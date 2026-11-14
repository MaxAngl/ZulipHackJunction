"""Grille fixe des formats de demande, classés par effort demandé au patient.

Le sujet d'une demande est libre, son format ne l'est pas : c'est ce qui permet de mesurer
l'effort et, plus tard, d'apprendre sur peu de données.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestFormat:
    key: str
    label: str
    effort: float  # entre 0 et 1
    hint: str  # consigne donnée au générateur


FORMATS: dict[str, RequestFormat] = {
    fmt.key: fmt
    for fmt in (
        RequestFormat("opinion", "Quick opinion", 0.15, "a quick opinion, answered in one message"),
        RequestFormat("memory", "Share a memory", 0.25, "share a memory or a short story"),
        RequestFormat("explain", "Explain", 0.40, "explain how to do something, e.g. a voice note"),
        RequestFormat("review", "Give feedback", 0.50, "look at something I made and comment"),
        RequestFormat("make", "Make and show", 0.70, "do a small thing and send the result"),
        RequestFormat("call", "Short call", 0.85, "a short live call"),
    )
}
DEFAULT_FORMAT = "opinion"

# Repérage du format d'un texte libre quand Gemini n'est pas disponible. Le premier motif gagne.
_FORMAT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("call", re.compile(r"\b(call|phone|video ?chat|meet|come over|together)\b")),
    ("make", re.compile(r"\b(could you (make|bake|cook|build|take|put together)|send me a photo)")),
    ("review", re.compile(r"\b(can i send|feedback|what you think of my|proofread|have a look)")),
    ("explain", re.compile(r"\b(explain|how do (you|i)|teach|walk me through|voice note)\b")),
    ("memory", re.compile(r"\b(remember|memory|first time|story|ever)\b")),
)


def effort_of(format_key: str) -> float:
    return FORMATS.get(format_key, FORMATS[DEFAULT_FORMAT]).effort


def label_of(format_key: str) -> str:
    return FORMATS.get(format_key, FORMATS[DEFAULT_FORMAT]).label


def guess_format(text: str) -> str:
    lowered = text.lower()
    for key, pattern in _FORMAT_PATTERNS:
        if pattern.search(lowered):
            return key
    return DEFAULT_FORMAT
