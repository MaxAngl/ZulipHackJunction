"""Les réseaux entraînés, vus par l'app : lire l'état, sortir la zone, noter, apprendre.

C'est la traduction de `ml.nets.runtime.Networks`, qui parle en tableaux pour des milliers de
patients, vers ce dont le backend a besoin pour un patient à la fois.

Les quatre gestes de la boucle :
- `reading` : θ → L, sur les 28 derniers relevés (l'autoencodeur) ;
- `zone` : la zone du patient, maintenant (le réseau B, seul) ;
- `reward` : la récompense de 0 à 100 entre deux relevés ;
- `learn` : le vecteur personnel du patient, réglé sur ses propres réactions (à travers A).
"""

from dataclasses import dataclass
from functools import cache

import numpy as np

from ml.formats import FORMATS
from ml.nets.features import SLOTS, WINDOW, context_features
from ml.nets.models import VECTOR_SIZE
from ml.nets.runtime import Networks
from ml.simulation.spec import COMPONENTS, CONTEXT_LENGTH
from ml.types import Zone, ZoneBox

Normal = tuple[np.ndarray, np.ndarray]

COMPONENT_LABELS: dict[str, str] = {
    "sleep": "Sleep",
    "rhythm": "Rhythm",
    "energy": "Energy",
    "calm": "Calm",
    "activity": "Activity",
    "engagement": "Engagement",
}


@dataclass(frozen=True)
class Reading:
    """Ce que les réseaux savent d'un patient à un instant : ses 28 derniers états."""

    at: int  # rang du relevé « maintenant »
    states: np.ndarray  # [28, 6]
    live: np.ndarray  # [12] comportement en direct
    index: np.ndarray  # [28] rang de chaque relevé, qui donne son heure
    context: np.ndarray  # [32] ce que le réseau A lit pour noter une demande

    @property
    def state(self) -> np.ndarray:
        """L(θ) maintenant : six composantes entre 0 et 1."""
        return self.states[-1]

    @property
    def wellbeing(self) -> float:
        """Un seul nombre pour l'affichage : la moyenne des six composantes."""
        return float(self.state.mean())


@dataclass(frozen=True)
class Outcome:
    """Une demande passée et ce qu'elle a donné : la matière dont le vecteur du patient apprend."""

    context: np.ndarray  # [32] le contexte au moment de la demande
    axes: tuple[float, ...]  # la position de la demande sur les six axes
    reward: float  # 0 à 100
    replied: bool


class Brain:
    def __init__(self, networks: Networks) -> None:
        self.networks = networks

    @property
    def parameters(self) -> int:
        return int(self.networks.meta.get("parameters", {}).get("total", 0))

    @property
    def reference(self) -> np.ndarray:
        """L_ref : la moyenne de chaque composante chez les personnes saines."""
        return self.networks.reference_mean

    def normal(self, theta: np.ndarray) -> Normal:
        """La normale d'une personne, d'après ses relevés de référence [relevés, signaux]."""
        mean, spread = self.networks.normal(theta[None])
        return mean[0], spread[0]

    def reading(self, theta: np.ndarray, normal: Normal, at: int | None = None) -> Reading:
        """Lit les 28 relevés qui finissent à `at` (par défaut, le dernier)."""
        at = len(theta) - 1 if at is None else at
        if at < CONTEXT_LENGTH - 1:
            raise ValueError("Il faut une semaine de relevés avant de lire l'état.")
        index = at + WINDOW
        states, live = self.networks.states(
            theta[None, index], (normal[0][None], normal[1][None]), index[None]
        )
        slot = np.array([at % SLOTS])
        context = context_features(states, live[:, -1], slot)[0]
        return Reading(at, states[0], live[0, -1], index, context)

    def zone(self, reading: Reading, vector: np.ndarray | None = None) -> Zone:
        """La zone du patient. Sans `vector` : le modèle général, sans rien de personnel."""
        general = self._box(reading, np.zeros(VECTOR_SIZE, dtype=np.float32))
        box = general if vector is None else self._box(reading, np.asarray(vector))
        low, high = box.low[0], box.high[0]
        return Zone(
            center=(low + high) / 2.0,
            half_width=(high - low) / 2.0,
            effort_max=_heaviest_format(box),
            common_center=(general.low[0] + general.high[0]) / 2.0,
            box=box,
        )

    def _box(self, reading: Reading, vector: np.ndarray) -> ZoneBox:
        low, high, startup = self.networks.zone(
            reading.states[None],
            reading.index[None],
            reading.live[None],
            vector[None].astype(np.float32),
        )
        return ZoneBox(
            low=tuple(round(float(value), 3) for value in low[0]),
            high=tuple(round(float(value), 3) for value in high[0]),
            startup_max=round(float(startup[0]), 3),
        )

    def distance(self, state: np.ndarray) -> float:
        """Distance à L_ref, en largeurs de la dispersion des personnes saines."""
        return float(self.networks.distance(state))

    def reward(self, before: Reading, after: Reading) -> float:
        """Récompense de 0 à 100 : s'est-il rapproché de L_ref entre les deux relevés ?"""
        return float(self.networks.reward(before.state, after.state))

    def learn(self, outcomes: list[Outcome], start: np.ndarray | None = None) -> np.ndarray:
        """Le vecteur du patient, réglé sur ses réactions. Sans réaction, il reste nul."""
        if not outcomes:
            return np.zeros(VECTOR_SIZE, dtype=np.float32)
        vectors = self.networks.fit_vectors(
            person=np.zeros(len(outcomes), dtype=int),
            context=np.stack([outcome.context for outcome in outcomes]),
            axes=np.array([outcome.axes for outcome in outcomes], dtype=np.float32),
            rewards=np.array([outcome.reward for outcome in outcomes]),
            replied=np.array([outcome.replied for outcome in outcomes]),
            n_people=1,
            start=None if start is None else np.asarray(start, dtype=np.float32)[None],
        )
        return vectors[0]

    def components(self, reading: Reading) -> list[tuple[str, str, float, float]]:
        """Pour l'affichage : clé, libellé, valeur et référence saine de chaque composante."""
        return [
            (key, COMPONENT_LABELS[key], float(value), float(healthy))
            for key, value, healthy in zip(COMPONENTS, reading.state, self.reference, strict=True)
        ]


def _heaviest_format(box: ZoneBox) -> float:
    """L'effort du format le plus lourd que la zone laisse passer : l'ancien « plafond d'effort »,
    gardé pour le générateur de texte, qui raisonne encore en formats."""
    allowed = [fmt.effort for fmt in FORMATS.values() if box.allows_costs(fmt.axes)]
    return max(allowed, default=min(fmt.effort for fmt in FORMATS.values()))


@cache
def brain() -> Brain:
    """Les réseaux versionnés dans `ml/weights`, chargés une seule fois."""
    return Brain(Networks.load())
