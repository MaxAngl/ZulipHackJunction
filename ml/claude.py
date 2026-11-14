"""Claude comme générateur de demandes (issue #74), avec le SDK officiel `anthropic`.

Même rôle que `ml/gemini.py` pour la génération : produire du JSON (les demandes, la relecture
d'un message). Pas d'embeddings chez Anthropic : la mesure de λ reste indépendante du
générateur (modèle local, `ml/embedding.py`). Toute erreur sort en ClaudeError : l'appelant
bascule alors sur la banque hors ligne, la démo ne casse jamais à cause du réseau ou d'un quota.

Clé : `ANTHROPIC_API_KEY` dans `.env` (jamais dans git). Modèle : `CLAUDE_MODEL`, par défaut
claude-opus-5-5 ; `claude-haiku-5-5` coûte environ 40 fois moins cher.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
TIMEOUT_SECONDS = 60.0
# Repli côté serveur si le modèle décline une demande (beta d'Anthropic) : il relance la même
# requête sur un autre modèle, choisi selon la catégorie du refus.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Tokens consommés depuis le lancement : pour annoncer le coût d'un essai (scripts, rapport).
usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}


class ClaudeError(Exception):
    """Erreur d'appel à Claude. `status` vaut 0 quand il n'y a pas eu de réponse HTTP."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Claude {status}: {message}")
        self.status = status
        self.message = message


def api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None


def is_configured() -> bool:
    return api_key() is not None


def generation_model() -> str:
    return os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Le schéma JSON tel que les sorties structurées de Claude l'acceptent.

    Chaque objet ferme ses propriétés (`additionalProperties: false`) et les rend toutes
    obligatoires ; les bornes numériques sont retirées (le code les vérifie de toute façon).
    """
    if not isinstance(schema, dict):
        return schema
    cleaned = {
        key: strict_schema(value) if isinstance(value, dict) else value
        for key, value in schema.items()
        if key not in ("minimum", "maximum")
    }
    if cleaned.get("type") == "object" and "properties" in cleaned:
        cleaned["properties"] = {
            name: strict_schema(value) for name, value in cleaned["properties"].items()
        }
        cleaned["required"] = list(cleaned["properties"])
        cleaned["additionalProperties"] = False
    if cleaned.get("type") == "array" and isinstance(cleaned.get("items"), dict):
        cleaned["items"] = strict_schema(cleaned["items"])
    return cleaned


def _client() -> Any:
    import anthropic

    return anthropic.Anthropic(api_key=api_key(), timeout=TIMEOUT_SECONDS, max_retries=2)


def generate_json(system: str, prompt: str, schema: dict[str, Any]) -> Any:
    """Demande une réponse JSON conforme à `schema` (sorties structurées de l'API)."""
    if not is_configured():
        raise ClaudeError(0, "ANTHROPIC_API_KEY absente")
    import anthropic

    try:
        response = _client().beta.messages.create(
            model=generation_model(),
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": strict_schema(schema)}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.APIStatusError as exc:
        raise ClaudeError(exc.status_code, str(exc.message)[:400]) from exc
    except anthropic.APIConnectionError as exc:  # réseau, délai dépassé
        raise ClaudeError(0, str(exc)) from exc

    usage["calls"] += 1
    usage["input_tokens"] += response.usage.input_tokens or 0
    usage["output_tokens"] += response.usage.output_tokens or 0
    if response.stop_reason == "refusal":
        raise ClaudeError(0, "demande déclinée par le modèle")
    if response.stop_reason == "max_tokens":
        raise ClaudeError(0, "réponse coupée (max_tokens)")
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClaudeError(0, "réponse non JSON") from exc
