"""Appariement patient–aidant par centres d'intérêt (issue #19).

1. Profil : chaque personne a un ensemble d'éléments d'intérêt, ses tags et chaque phrase de son
   commentaire libre, avec un vecteur par élément (embedding Gemini, ou repli hors ligne).
2. Score : pour chaque élément du patient, le meilleur cosinus avec un élément de l'aidant, puis
   la moyenne. Tout est comparé à tout : un « ski » en tag retrouve un « ski » écrit en
   commentaire. Seule compte la couverture des intérêts du patient : un aidant qui a d'autres
   intérêts en plus n'est pas pénalisé.
3. Appariement : mariages stables (Gale-Shapley), les patients proposent. Un patient classe les
   aidants par score ; un aidant classe les patients par score + bonus d'attente, pour servir
   d'abord ceux qui attendent depuis longtemps.
"""

import hashlib
import logging
import math
import re
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ml import gemini

logger = logging.getLogger(__name__)

OFFLINE_PROVIDER = "offline"
OFFLINE_DIMENSIONS = 512

# Bonus d'attente : il grandit avec l'attente et plafonne à WAIT_WEIGHT au bout de
# WAIT_FULL_DAYS jours. Le score d'intérêts va de 0 à 1 : avec 0,3, une semaine d'attente pèse
# autant que 0,3 point de proximité. À régler avec l'équipe.
WAIT_WEIGHT = 0.3
WAIT_FULL_DAYS = 7.0
SECONDS_PER_DAY = 86_400.0


@dataclass(frozen=True)
class InterestProfile:
    """Les éléments d'intérêt d'une personne et leurs vecteurs, de norme 1.

    `provider` dit d'où viennent les vecteurs (`gemini:<modèle>` ou `offline`) : deux profils ne
    se comparent que s'ils viennent du même endroit.
    """

    items: tuple[str, ...]
    vectors: tuple[tuple[float, ...], ...]
    provider: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": list(self.items),
            "vectors": [list(vector) for vector in self.vectors],
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterestProfile":
        return cls(
            items=tuple(data["items"]),
            vectors=tuple(tuple(vector) for vector in data["vectors"]),
            provider=data["provider"],
        )


def interest_items(tags: Sequence[str], comment: str = "") -> list[str]:
    """Les tags, puis chaque phrase du commentaire libre, sans doublon."""
    sentences = re.split(r"[.!?;\n]+", comment)
    cleaned = (" ".join(item.split()).lower() for item in [*tags, *sentences])
    return list(dict.fromkeys(item for item in cleaned if item))


def build_profile(tags: Sequence[str], comment: str = "") -> InterestProfile:
    """Calcule le profil d'une personne. Gemini si possible, sinon le repli hors ligne."""
    items = interest_items(tags, comment)
    if not items:
        return InterestProfile((), (), OFFLINE_PROVIDER)
    try:
        vectors = gemini.embed(items)
    except gemini.GeminiError as exc:
        logger.info("Embeddings Gemini indisponibles, repli hors ligne : %s", exc)
        return offline_profile(items)
    return InterestProfile(
        items=tuple(items),
        vectors=tuple(_normalize(vector) for vector in vectors),
        provider=f"gemini:{gemini.embedding_model()}",
    )


def offline_profile(items: Sequence[str]) -> InterestProfile:
    """Vecteurs sans réseau : trigrammes de lettres hachés. « garden » et « gardening » se
    ressemblent, « ski » et « chess » non. Aucun sens : ce n'est qu'un filet de sécurité."""
    return InterestProfile(
        items=tuple(items),
        vectors=tuple(_offline_vector(item) for item in items),
        provider=OFFLINE_PROVIDER,
    )


def coverage(patient: InterestProfile, helper: InterestProfile) -> float:
    """Moyenne, sur les éléments du patient, de leur meilleur cosinus chez l'aidant (0 à 1)."""
    if not patient.vectors or not helper.vectors:
        return 0.0
    best = [max(_dot(mine, theirs) for theirs in helper.vectors) for mine in patient.vectors]
    return max(0.0, sum(best) / len(best))


def wait_bonus(waiting_seconds: float) -> float:
    days = max(0.0, waiting_seconds) / SECONDS_PER_DAY
    return WAIT_WEIGHT * min(days / WAIT_FULL_DAYS, 1.0)


def stable_match(
    patients: dict[str, InterestProfile],
    helpers: dict[str, InterestProfile],
    waiting_seconds: dict[str, float],
) -> dict[str, str]:
    """Mariages stables, les patients proposent. Renvoie {patient: aidant}.

    Un aidant prend au plus un patient. S'il y a plus de patients que d'aidants, ceux qui
    restent seuls attendent : leur bonus d'attente grandit et les fera passer devant plus tard.
    À égalité, le premier dans l'ordre des dictionnaires l'emporte.
    """
    patients, helpers = _comparable(patients, helpers)
    score = {(p, h): coverage(patients[p], helpers[h]) for p in patients for h in helpers}
    prefers = {p: sorted(helpers, key=lambda h, p=p: -score[p, h]) for p in patients}

    def helper_value(helper: str, patient: str) -> float:
        return score[patient, helper] + wait_bonus(waiting_seconds.get(patient, 0.0))

    proposals = dict.fromkeys(patients, 0)
    partner: dict[str, str] = {}  # aidant -> patient
    free = deque(patients)
    while free:
        patient = free.popleft()
        if proposals[patient] >= len(prefers[patient]):
            continue  # a demandé à tous les aidants : reste seul cette fois
        helper = prefers[patient][proposals[patient]]
        proposals[patient] += 1
        current = partner.get(helper)
        if current is None:
            partner[helper] = patient
        elif helper_value(helper, patient) > helper_value(helper, current):
            partner[helper] = patient
            free.append(current)
        else:
            free.append(patient)
    return {patient: helper for helper, patient in partner.items()}


def _comparable(
    patients: dict[str, InterestProfile], helpers: dict[str, InterestProfile]
) -> tuple[dict[str, InterestProfile], dict[str, InterestProfile]]:
    """Si les profils ne viennent pas tous du même endroit, tout le monde passe hors ligne."""
    providers = {profile.provider for profile in [*patients.values(), *helpers.values()]}
    if len(providers) <= 1:
        return patients, helpers

    def offline(group: dict[str, InterestProfile]) -> dict[str, InterestProfile]:
        return {key: offline_profile(profile.items) for key, profile in group.items()}

    return offline(patients), offline(helpers)


def _offline_vector(text: str) -> tuple[float, ...]:
    counts = [0.0] * OFFLINE_DIMENSIONS
    for word in re.findall(r"\w+", text.lower()):
        padded = f" {word} "
        for start in range(len(padded) - 2):
            digest = hashlib.blake2b(padded[start : start + 3].encode(), digest_size=4).digest()
            counts[int.from_bytes(digest, "big") % OFFLINE_DIMENSIONS] += 1.0
    return _normalize(counts)


def _normalize(vector: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in vector))
    return tuple(value / norm for value in vector) if norm else tuple(vector)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
