"""Vecteurs de texte : embeddings Gemini, modèle local, ou vecteur lexical en dernier recours.

On ne mélange jamais deux sources dans une même mesure : un texte et les deux centres d'intérêt
auxquels on le compare passent toujours par la même.

Le modèle local (issue #69) tourne sur le CPU, sans clé ni quota : c'est la mesure par défaut
quand Gemini n'est pas configuré. Il est téléchargé une fois (~120 Mo) dans le cache Hugging Face
au premier usage. `NEEDED_LOCAL_EMBEDDINGS=off` le coupe (les tests le font), et toute erreur de
chargement ramène à la mesure lexicale, sans casser l'app.
"""

import logging
import math
import os
import threading
from typing import Literal

from ml import gemini, lexicon

logger = logging.getLogger(__name__)

Measure = Literal["gemini", "local", "offline"]  # offline = mesure lexicale par mots-clés

LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LOCAL_SWITCH = "NEEDED_LOCAL_EMBEDDINGS"
_MAX_TOKENS = 128

_gemini_cache: dict[str, list[float]] = {}
_local_cache: dict[str, list[float]] = {}
_local: dict[str, object] = {}  # "model", "tokenizer", ou "failed"
_local_lock = threading.Lock()


def cosine(a: list[float], b: list[float]) -> float:
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def lexical_vector(text: str, interests: list[str]) -> list[float]:
    """Une dimension par centre d'intérêt : le poids de ses mots-clés présents dans le texte."""
    return [lexicon.weighted_hits(text, name) for name in interests]


def local_enabled() -> bool:
    return os.environ.get(LOCAL_SWITCH, "").strip().lower() not in ("off", "0", "false", "no")


def _load_local() -> bool:
    """Charge le modèle local une seule fois. False s'il est coupé ou indisponible."""
    if not local_enabled():
        return False
    with _local_lock:
        if "failed" in _local:
            return False
        if "model" in _local:
            return True
        try:
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
            from transformers import AutoModel, AutoTokenizer

            _local["tokenizer"] = AutoTokenizer.from_pretrained(LOCAL_MODEL)
            _local["model"] = AutoModel.from_pretrained(LOCAL_MODEL).eval()
        except Exception as exc:  # réseau, disque, bibliothèque : l'app continue sans
            logger.warning("Modèle d'embeddings local indisponible, mesure lexicale : %s", exc)
            _local["failed"] = True
            return False
        return True


def local_available() -> bool:
    """Le modèle local est-il utilisable ? Le charge au premier appel."""
    return _load_local()


def local_embed(texts: list[str]) -> list[list[float]]:
    """Vecteurs de norme 1 du modèle local (moyenne des tokens, comme sentence-transformers)."""
    missing = [text for text in dict.fromkeys(texts) if text not in _local_cache]
    if missing:
        if not _load_local():
            raise RuntimeError("modèle d'embeddings local indisponible")
        import torch

        tokenizer, model = _local["tokenizer"], _local["model"]
        batch = tokenizer(  # type: ignore[operator]
            missing, padding=True, truncation=True, max_length=_MAX_TOKENS, return_tensors="pt"
        )
        with torch.no_grad():
            hidden = model(**batch).last_hidden_state  # type: ignore[operator]
        mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        vectors = torch.nn.functional.normalize(pooled, dim=1).tolist()
        for text, vector in zip(missing, vectors, strict=True):
            _local_cache[text] = vector
    return [_local_cache[text] for text in texts]


def measure_kind(generator: str) -> Measure:
    """Quelle mesure pour des textes venus de ce générateur.

    Gemini mesure ce qu'il a écrit avec ses propres embeddings. Sinon, le modèle local s'il est
    là, et la mesure lexicale en dernier recours.
    """
    if generator == "gemini":
        return "gemini"
    return "local" if local_available() else "offline"


def embed_texts(texts: list[str], provider: Measure, interests: list[str]) -> list[list[float]]:
    """Un vecteur par texte. `interests` fixe les dimensions de la mesure lexicale."""
    if provider == "offline":
        return [lexical_vector(text, interests) for text in texts]
    if provider == "local":
        return local_embed(texts)
    missing = [text for text in dict.fromkeys(texts) if text not in _gemini_cache]
    if missing:
        for text, vector in zip(missing, gemini.embed(missing), strict=True):
            _gemini_cache[text] = vector
    return [_gemini_cache[text] for text in texts]
