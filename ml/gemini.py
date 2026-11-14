"""Client REST minimal pour l'API Gemini, avec la bibliothèque standard uniquement.

Deux usages : générer du JSON (les demandes, la relecture d'un message) et calculer des
embeddings (la mesure sur l'axe λ). Toute erreur sort en GeminiError : l'appelant bascule alors
sur le mode hors ligne, la démo ne doit jamais casser à cause du réseau ou d'un quota.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-flash-lite-latest"
DEFAULT_EMBED_MODEL = "gemini-embedding-001"
TIMEOUT_SECONDS = 15
RETRY_STATUSES = (429, 500, 503)
RETRY_PAUSES = (0.6, 1.5)  # secondes avant le deuxième et le troisième essai d'embedding


class GeminiError(Exception):
    """Erreur d'appel à Gemini. `status` vaut 0 quand il n'y a pas eu de réponse HTTP."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Gemini {status}: {message}")
        self.status = status
        self.message = message


def api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def is_configured() -> bool:
    return api_key() is not None


def generation_model() -> str:
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def embedding_model() -> str:
    return os.environ.get("GEMINI_EMBED_MODEL") or DEFAULT_EMBED_MODEL


def api_root() -> str:
    return (
        os.environ.get("GEMINI_API_ROOT") or os.environ.get("GEMINI_BASE_URL") or API_ROOT
    ).rstrip("/")


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    key = api_key()
    if key is None:
        raise GeminiError(0, "GEMINI_API_KEY absente")
    clean_path = path.lstrip("/")
    url = f"{api_root()}/{clean_path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise GeminiError(exc.code, detail) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GeminiError(0, str(exc)) from exc


def _first_text(data: dict[str, Any]) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiError(0, "réponse sans texte (bloquée ou vide)") from exc
    return "".join(part.get("text", "") for part in parts if not part.get("thought"))


def _parse_json_text(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise GeminiError(0, "réponse non JSON") from None
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise GeminiError(0, "réponse non JSON") from exc


def generate_json(system: str, prompt: str, schema: dict[str, Any]) -> Any:
    """Demande une réponse JSON conforme à `schema`.

    Les noms de champs de configuration changent d'une version de l'API à l'autre : en cas de
    refus (400), on réessaie avec une configuration plus simple avant d'abandonner.
    Si le modèle configuré est introuvable (404), on essaie les modèles standards de secours.
    """
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    json_mode = {"responseMimeType": "application/json", "temperature": 0.9}
    configs: list[dict[str, Any]] = [
        {**json_mode, "responseJsonSchema": schema, "thinkingConfig": {"thinkingLevel": "LOW"}},
        {**json_mode, "responseJsonSchema": schema},
        json_mode,
    ]
    model = generation_model()
    candidates = list(
        dict.fromkeys(
            [model, "gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-flash-latest"]
        )
    )
    last_error = GeminiError(0, "aucune tentative")
    for m in candidates:
        for config in configs:
            try:
                path = f"models/{m}:generateContent"
                data = _post(path, {**body, "generationConfig": config})
                return _parse_json_text(_first_text(data))
            except GeminiError as exc:
                last_error = exc
                if exc.status in (404, 503, 429):
                    # Modèle surchargé, indisponible ou quota : essayer le modèle suivant
                    break
                if exc.status != 400:
                    raise
                logger.warning(
                    "Gemini a refusé la configuration, nouvel essai plus simple : %s", exc
                )
    raise last_error


def _post_patiently(path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Comme `_post`, mais réessaie deux fois sur une surcharge passagère (503, 429, 500).

    Pour les embeddings : contrairement à la génération, on ne peut pas se replier sur un autre
    modèle sans changer l'échelle de la mesure de position. Sans cela, une seule surcharge fait
    retomber toute la mesure sur les mots-clés.
    """
    for pause in (*RETRY_PAUSES, None):
        try:
            return _post(path, body)
        except GeminiError as exc:
            if exc.status not in RETRY_STATUSES or pause is None:
                raise
            logger.info("Gemini %s sur les embeddings, nouvel essai dans %.1f s", exc.status, pause)
            time.sleep(pause)
    raise GeminiError(0, "aucune réponse")  # jamais atteint : la dernière passe lève toujours


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Calcul d'embedding pour un lot de textes."""
    model = embedding_model()
    variants: list[dict[str, Any]] = [
        {"taskType": "SEMANTIC_SIMILARITY", "outputDimensionality": 768},
        {},
    ]
    candidates = list(dict.fromkeys([model, "gemini-embedding-001", "text-embedding-004"]))
    last_error = GeminiError(0, "aucune tentative")
    for m in candidates:
        for extra in variants:
            requests = [
                {"model": f"models/{m}", "content": {"parts": [{"text": text}]}, **extra}
                for text in texts
            ]
            try:
                data = _post_patiently(f"models/{m}:batchEmbedContents", {"requests": requests})
            except GeminiError as exc:
                last_error = exc
                if exc.status == 404:
                    break
                if exc.status != 400:
                    raise
                continue
            vectors = [item.get("values", []) for item in data.get("embeddings", [])]
            if len(vectors) != len(texts) or not all(vectors):
                raise GeminiError(0, "réponse d'embedding inattendue")
            return vectors
    raise last_error


def embed(texts: list[str]) -> list[list[float]]:
    """Un vecteur par texte, dans l'ordre (découpé par lots pour ne pas dépasser la limite)."""
    if not texts:
        return []
    chunk_size = 50
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), chunk_size):
        chunk = texts[i : i + chunk_size]
        all_vectors.extend(_embed_batch(chunk))
    return all_vectors
