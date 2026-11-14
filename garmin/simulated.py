"""Montre simulée : un relevé tiré du générateur de l'équipe, pour la démo si Garmin lâche."""

import numpy as np

from garmin.signals import WATCH_SIGNALS, Reading
from ml.simulation.people import draw_people, observe
from ml.simulation.spec import COMPONENTS, SIGNAL_NAMES, SNAPSHOT_HOURS


def simulated_reading(hour: float, level: float | None = None, seed: int | None = None) -> Reading:
    """Relevé d'un patient simulé, au relevé de la journée le plus proche de `hour`.

    `level` fixe les six composantes de son état (0 = au plus mal, 1 = au mieux) ;
    sans lui, l'état est tiré comme pour un patient du générateur.
    """
    rng = np.random.default_rng(seed)
    people = draw_people(rng, n_people=1, n_days=1, healthy_share=0.0)
    state = people.natural
    if level is not None:
        state = np.full((1, 1, len(COMPONENTS)), float(np.clip(level, 0.02, 0.98)))
    slot = int(np.argmin(np.abs(np.asarray(SNAPSHOT_HOURS) - hour)))
    values = observe(rng, people, state)[0, slot]
    reading = dict(zip(SIGNAL_NAMES, values.tolist(), strict=True))
    return {name: None if np.isnan(reading[name]) else reading[name] for name in WATCH_SIGNALS}
