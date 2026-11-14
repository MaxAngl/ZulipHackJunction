"""Un patient virtuel : ce qui tient lieu de montre et de corps tant qu'aucune n'est branchée.

SIMULÉ. Il produit les 25 signaux de θ, jour après jour, à partir d'un état caché et de règles
cachées tirées au hasard, exactement comme les patients qui ont servi à entraîner les réseaux
(`ml/simulation`). Les réseaux ne voient que ses relevés : ni son état, ni ses règles.

Une demande agit sur son état selon ses règles, puis une journée passe : c'est ce qui permet de
mesurer une récompense vingt-quatre heures après, comme dans docs/modele.md.
"""

import numpy as np

from ml.simulation import patient
from ml.simulation.people import PATIENT, People, draw_people, observe
from ml.simulation.spec import COMPONENTS, SIGNALS, SNAPSHOT_HOURS, signal_index

REFERENCE_DAYS = 14  # jours vécus avant la première demande : la période de référence
RECENT_DAYS = 7  # jours réécrits quand on change son niveau à la main
DAILY_NOISE = 0.02  # ce dont son état bouge tout seul d'un jour à l'autre
PERSISTENCE = 0.7


class VirtualPatient:
    """Un patient simulé de bout en bout. La même graine redonne exactement le même patient."""

    def __init__(self, seed: int, level: float = 0.55) -> None:
        self._rng = np.random.default_rng(seed)
        drawn = draw_people(self._rng, 1, 1, healthy_share=0.0)
        self._traits = drawn.traits
        self._rules = patient.draw_rules(self._rng, 1)
        # Chaque composante s'écarte un peu du niveau général : personne n'est uniforme.
        self._offsets = self._rng.normal(0.0, 0.05, len(COMPONENTS))
        self._mood = np.zeros(
            len(COMPONENTS)
        )  # ce qui bouge tout seul, corrélé d'un jour à l'autre
        self._boost = np.zeros(len(COMPONENTS))  # ce qui reste des demandes passées
        self.level = float(level)
        # Dernière valeur connue de chaque signal réellement mesuré (la montre, par exemple) :
        # elle remplace celle du simulateur dans chaque relevé, jusqu'à la mesure suivante.
        self._real: dict[str, float] = {}
        self.theta = np.empty((0, len(SIGNALS)), dtype=np.float32)
        self.states: list[np.ndarray] = []  # l'état caché de chaque jour vécu
        for _ in range(REFERENCE_DAYS):
            self._live_one_day()

    # --- Ce que l'app peut lire --------------------------------------------------------------

    @property
    def days(self) -> int:
        return len(self.states)

    @property
    def now(self) -> int:
        """Rang du dernier relevé."""
        return len(self.theta) - 1

    @property
    def hidden_state(self) -> np.ndarray:
        """La vérité cachée du jour. Réservée à l'affichage de démonstration."""
        return self.states[-1]

    # --- Ce qui lui arrive -------------------------------------------------------------------

    def set_level(self, level: float) -> None:
        """Change son état de fond, comme si la dernière semaine s'était passée à ce niveau."""
        self.level = float(np.clip(level, 0.02, 0.98))
        self._boost[:] = 0.0
        kept = max(REFERENCE_DAYS, self.days - RECENT_DAYS)
        rewritten = self.days - kept
        self.theta = self.theta[: kept * len(SNAPSHOT_HOURS)]
        self.states = self.states[:kept]
        for _ in range(max(rewritten, RECENT_DAYS)):
            self._live_one_day()

    def receive(
        self, axes: np.ndarray, replied: bool, measured: dict[str, float] | None = None
    ) -> tuple[float, float]:
        """Une demande, sa réponse ou son silence, puis une journée passe.

        `axes` : la position de la demande sur les six axes. `measured` : des signaux réellement
        relevés (par exemple la frappe du patient dans l'app), qui remplacent ceux du simulateur
        dans les relevés du lendemain. Renvoie la vérité cachée de cette demande pour ce
        patient : à quel point elle lui convenait, et de combien elle dépassait ce qu'il supporte.
        """
        state = self.hidden_state[None, :]
        effect, fit, overload = patient.effect_of(
            self._rules, state, np.asarray(axes, dtype=float)[None, :], np.array([replied])
        )
        self._boost = patient.EFFECT_DECAY * self._boost + effect[0]
        self._live_one_day(decay=False, measured=measured)
        return float(fit[0]), float(overload[0])

    def rest(self) -> None:
        """Une journée sans demande."""
        self._live_one_day()

    def measure(self, values: dict[str, float]) -> None:
        """Des signaux réellement relevés, par exemple par la montre, à l'instant présent.

        Ils remplacent ceux du simulateur dans le dernier relevé, puis restent leur dernière
        valeur connue dans les relevés suivants (docs/modele.md, section 11). Le simulateur ne
        complète que ce qui n'est pas mesuré.
        """
        self._real.update(values)
        _overwrite(self.theta[-1:], values)

    # --- Intérieur ---------------------------------------------------------------------------

    def _live_one_day(self, decay: bool = True, measured: dict[str, float] | None = None) -> None:
        if decay and self.states:
            self._boost = patient.EFFECT_DECAY * self._boost
        noise = self._rng.normal(0.0, DAILY_NOISE, len(COMPONENTS))
        self._mood = PERSISTENCE * self._mood + noise
        state = np.clip(self.level + self._offsets + self._mood + self._boost, 0.02, 0.98)
        one = People(
            group=np.array([PATIENT], dtype=np.int8),
            course=np.zeros(1, dtype=np.int8),
            natural=state[None, None, :],
            traits=self._traits,
        )
        snapshots = observe(self._rng, one, state[None, None, :])[0]
        _overwrite(snapshots, {**self._real, **(measured or {})})
        self.theta = np.concatenate([self.theta, snapshots])
        self.states.append(state)


def _overwrite(snapshots: np.ndarray, values: dict[str, float]) -> None:
    """Remplace des colonnes de relevés par des valeurs mesurées, ramenées à leurs bornes."""
    for name, value in values.items():
        signal = SIGNALS[signal_index(name)]
        snapshots[:, signal_index(name)] = np.clip(value, signal.low, signal.high)
