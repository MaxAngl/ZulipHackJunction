"""Les politiques comparées en boucle fermée (docs/modele.md, section 7).

Une politique choisit une zone par patient à partir des relevés déjà faits :

- `RandomZones` (dans `ml.simulation.episodes`) : une zone au hasard ;
- `FixedRule` : la règle écrite à la main du code actuel, étendue aux six axes ;
- `LearnedPolicy` : le réseau B, avec ou sans le vecteur personnel du patient ;
- `Oracle` : il lit l'état caché et les règles du patient simulé. C'est le plafond, que
  personne ne peut atteindre dans la vraie vie.
"""

import numpy as np

from ml.nets.features import REFERENCE_DAYS, SLOTS, WINDOW, context_features
from ml.nets.models import CEILING, HALF_MIN, STARTUP_CEILING, STARTUP_FLOOR, VECTOR_SIZE
from ml.nets.runtime import Networks
from ml.simulation import patient
from ml.simulation.episodes import Moment, Zones
from ml.simulation.spec import CONTEXT_DAYS, INTERVAL_AXES

SETTLE_DAYS = 2  # une demande est notée deux jours après : toutes ses mesures sont alors passées


def _nothing(n_people: int) -> Zones:
    """Avant la première semaine, personne ne reçoit de demande : la zone ne sert pas."""
    return (
        np.zeros((n_people, INTERVAL_AXES)),
        np.zeros((n_people, INTERVAL_AXES)),
        np.zeros(n_people),
    )


class _Reader:
    """Lit θ comme l'app le ferait : normale de la personne, puis L sur les 28 derniers relevés."""

    def __init__(self, networks: Networks) -> None:
        self.networks = networks
        self.normal: tuple[np.ndarray, np.ndarray] | None = None

    def read(self, moment: Moment) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """États [n, 28, 6], comportement en direct [n, 12] et rang des 28 relevés [n, 28]."""
        seen = moment.theta[:, : (moment.day + 1) * SLOTS]
        if self.normal is None or moment.day < REFERENCE_DAYS:
            self.normal = self.networks.normal(seen)  # figée après la période de référence
        index = (moment.day * SLOTS + moment.slot)[:, None] + WINDOW
        window = seen[np.arange(len(index))[:, None], index]
        states, live = self.networks.states(window, self.normal, index)
        return states, live[:, -1], index


class FixedRule(_Reader):
    """La règle du code actuel (`ml.model.zone_for`) : tout vient d'un seul nombre, l'état moyen.

    Position sur l'axe des intérêts : 1 − 0,6 × état. Plafond d'effort : 0,25 + 0,75 × état,
    appliqué ici aux quatre axes de coût. L'axe concret, que l'ancienne règle ne connaît pas,
    reçoit un intervalle large et fixe.
    """

    def zones(self, moment: Moment) -> Zones:
        n_people = len(moment.slot)
        if moment.day < CONTEXT_DAYS:
            return _nothing(n_people)
        states, _, _ = self.read(moment)
        wellbeing = states[:, -1].mean(axis=1)
        center = np.clip(1.0 - 0.6 * wellbeing, 0.18, 0.82)
        effort = np.clip(0.25 + 0.75 * wellbeing, 0.1, 1.0)
        low = np.full((n_people, INTERVAL_AXES), 0.05)
        high = np.minimum(effort[:, None], np.array(CEILING)[None, :])
        low[:, 0], high[:, 0] = center - 0.18, center + 0.18
        low[:, 1], high[:, 1] = 0.25, 0.85
        return low, high, np.minimum(effort, STARTUP_CEILING)

    def feedback(self, moment: Moment, axes: np.ndarray, reaction: patient.Reaction) -> None:
        return None


class Oracle:
    """Lit la vérité cachée : ce qui convient au patient et ce qu'il supporte aujourd'hui."""

    def zones(self, moment: Moment) -> Zones:
        capacity = patient.capacities(moment.rules, moment.hidden_state)
        interest, concrete = patient.sweet_spots(moment.rules, moment.hidden_state)
        ceiling = np.array(CEILING)
        center = np.column_stack([interest, concrete])
        center = np.clip(center, HALF_MIN, 1.0 - HALF_MIN)
        # Sur les axes de coût : juste en dessous de ce qu'il supporte.
        top = np.clip(np.minimum(capacity[:, :3], ceiling[2:]), 2 * HALF_MIN, None)
        low = np.column_stack([center - HALF_MIN, top - 2 * HALF_MIN])
        high = np.column_stack([center + HALF_MIN, top])
        return low, high, np.full(len(capacity), STARTUP_FLOOR)

    def feedback(self, moment: Moment, axes: np.ndarray, reaction: patient.Reaction) -> None:
        return None


class LearnedPolicy(_Reader):
    """Le réseau B décide seul. Le réseau A ne sert qu'à régler le vecteur de chaque patient.

    Avec `personal=False`, le vecteur reste nul : c'est le modèle général, celui que reçoit un
    nouveau patient.
    """

    def __init__(self, networks: Networks, personal: bool = True, refit_every: int = 2) -> None:
        super().__init__(networks)
        self.personal = personal
        self.refit_every = refit_every
        self.measure = networks.meta.get("trained_on", {}).get("reward_measure", "slot")
        self.vectors: np.ndarray | None = None
        self._context: np.ndarray | None = None
        self._waiting: list[tuple[int, np.ndarray, ...]] = []
        self._memory: list[tuple[np.ndarray, ...]] = []

    def zones(self, moment: Moment) -> Zones:
        n_people = len(moment.slot)
        if self.vectors is None:
            self.vectors = np.zeros((n_people, VECTOR_SIZE), dtype=np.float32)
        if moment.day < CONTEXT_DAYS:
            return _nothing(n_people)
        states, live, index = self.read(moment)
        self._context = context_features(states, live, moment.slot)
        if self.personal:
            self._settle(moment)
            if moment.day % self.refit_every == 0 and self._memory:
                past = [np.concatenate(part) for part in zip(*self._memory, strict=True)]
                self.vectors = self.networks.fit_vectors(
                    *past, n_people, start=self.vectors, steps=30
                )
        return self.networks.zone(states, index, live, self.vectors)

    def feedback(self, moment: Moment, axes: np.ndarray, reaction: patient.Reaction) -> None:
        if not self.personal or moment.day < CONTEXT_DAYS or self._context is None:
            return
        asked = moment.asked
        at = (moment.day * SLOTS + moment.slot)[asked]
        self._waiting.append(
            (
                moment.day,
                np.flatnonzero(asked),
                self._context[asked],
                axes[asked],
                at,
                reaction.replied[asked],
            )
        )

    def _settle(self, moment: Moment) -> None:
        """Note les demandes assez anciennes, avec la même mesure qu'à l'entraînement."""
        assert self.normal is not None
        due = [batch for batch in self._waiting if batch[0] <= moment.day - SETTLE_DAYS]
        self._waiting = [batch for batch in self._waiting if batch[0] > moment.day - SETTLE_DAYS]
        for day, person, context, axes, at, replied in due:
            if len(person) == 0:
                continue
            if self.measure == "day":
                today = day * SLOTS + np.arange(SLOTS)
                index = np.concatenate([today, today + SLOTS])
                index = np.broadcast_to(index, (len(person), 2 * SLOTS))
            else:
                index = np.stack([at, at + SLOTS], axis=1)
            window = moment.theta[person[:, None], index]
            normal = (self.normal[0][person], self.normal[1][person])
            states, _ = self.networks.states(window, normal, index)
            half = index.shape[1] // 2
            before, after = states[:, :half].mean(axis=1), states[:, half:].mean(axis=1)
            rewards = self.networks.reward(before, after)
            self._memory.append((person, context, axes, rewards, replied))
