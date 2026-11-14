"""Vecteurs de texte : embeddings Gemini, ou vecteur lexical en mode hors ligne.

On ne mélange jamais les deux dans une même mesure : un texte et les deux centres d'intérêt
auxquels on le compare passent toujours par le même fournisseur.
"""

import math

from ml import gemini, lexicon
from ml.types import Provider

_gemini_cache: dict[str, list[float]] = {}


def cosine(a: list[float], b: list[float]) -> float:
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def lexical_vector(text: str, interests: list[str]) -> list[float]:
    """Une dimension par centre d'intérêt : le poids de ses mots-clés présents dans le texte."""
    return [lexicon.weighted_hits(text, name) for name in interests]


def embed_texts(texts: list[str], provider: Provider, interests: list[str]) -> list[list[float]]:
    """Un vecteur par texte. `interests` fixe les dimensions du mode hors ligne."""
    if provider == "offline":
        return [lexical_vector(text, interests) for text in texts]
    missing = [text for text in dict.fromkeys(texts) if text not in _gemini_cache]
    if missing:
        for text, vector in zip(missing, gemini.embed(missing), strict=True):
            _gemini_cache[text] = vector
    return [_gemini_cache[text] for text in texts]
