"""Point d'entrée du module ML.

CONTRAT avec backend/ : la signature de `predict` et le type `Prediction`.
L'intérieur se change librement. Changer la signature = prévenir l'équipe (voir AGENTS.md).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Prediction:
    label: str
    score: float  # toujours entre 0 et 1


def predict(text: str) -> Prediction:
    """Placeholder à remplacer par le vrai modèle, en gardant la signature.

    Charger le modèle une seule fois (au niveau du module ou via functools.cache),
    jamais à chaque appel.
    """
    positive_words = {"bien", "super", "génial", "top", "good", "great"}
    words = text.lower().split()
    hits = sum(word in positive_words for word in words)
    score = hits / len(words) if words else 0.0
    label = "positive" if score > 0 else "neutral"
    return Prediction(label=label, score=round(score, 3))
