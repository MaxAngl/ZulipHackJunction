"""Récompense : de 0 à 100, selon que le patient se rapproche ou s'éloigne de L_ref.

L_ref est l'état des personnes saines : une moyenne et une dispersion par composante. La
distance d'un état à L_ref se compte en « largeurs » de cette dispersion, ce qui en fait une
région plutôt qu'un point : une personne saine typique est à une distance proche de 1.

La récompense est l'amélioration relative de cette distance entre avant et après la demande :
    gain = (d_avant − d_après) / (d_avant + 1)
    récompense = 50 + 150 · gain, ramenée entre 0 et 100
50 veut dire « rien n'a changé ». Le « + 1 » évite qu'un patient déjà tout proche de L_ref
fasse exploser le rapport. Une amélioration d'un tiers donne 100.

Dans les données simulées, la récompense est calculée sur l'état caché. Une fois
l'autoencodeur entraîné, la même formule s'appliquera à L(θ).
"""

import numpy as np

REWARD_GAIN = 150.0
NEUTRAL_REWARD = 50.0


def reference(healthy_states: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """L_ref : moyenne et dispersion de l'état des personnes saines, par composante."""
    flat = healthy_states.reshape(-1, healthy_states.shape[-1])
    return flat.mean(axis=0), np.clip(flat.std(axis=0), 1e-3, None)


def distance(state: np.ndarray, mean: np.ndarray, spread: np.ndarray) -> np.ndarray:
    """Distance d'un état à L_ref, en largeurs de la dispersion saine."""
    return np.sqrt((((state - mean) / spread) ** 2).mean(axis=-1))


def reward(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """Récompense de 0 à 100 à partir des distances à L_ref avant et après."""
    gain = (before - after) / (before + 1.0)
    return np.clip(NEUTRAL_REWARD + REWARD_GAIN * gain, 0.0, 100.0)
