"""Des relevés bruts θ aux entrées des réseaux. Numpy seul : aucun poids appris ici.

Chaque signal est donné deux fois à l'autoencodeur :
- par rapport à tout le monde (`g`), ce qui garde le niveau absolu de la personne ;
- par rapport à sa propre normale (`p`), ce qui efface ses habitudes.
Un troisième nombre dit si le signal est présent (`m`).

La normale d'une personne est la moyenne et la dispersion de chacun de ses signaux sur une
période de référence, ses quatorze premiers jours. Elle est ensuite figée : une dégradation
lente ne doit pas devenir sa nouvelle normale.
"""

import warnings

import numpy as np

from ml.simulation.spec import CONTEXT_LENGTH, SIGNALS, SNAPSHOT_HOURS, modality_indices

N_SIGNALS = len(SIGNALS)
SLOTS = len(SNAPSHOT_HOURS)
LOG = np.array([signal.log for signal in SIGNALS])
REFERENCE_DAYS = 14
REFERENCE_SNAPSHOTS = REFERENCE_DAYS * SLOTS
CLIP = 5.0  # au-delà de cinq écarts-types, une valeur n'apporte plus rien
MIN_OBSERVATIONS = 5  # en dessous, la normale de la personne est celle de tout le monde

# Le comportement « en direct » donné à A et à B en plus de L : les signaux de l'app et de la
# frappe au moment de la décision, c'est-à-dire tout ce qui ne vient pas de la montre.
LIVE_COLUMNS: list[int] = [
    column
    for modality, columns in modality_indices().items()
    if modality != "watch"
    for column in columns
]
LIVE_SIZE = 2 * len(LIVE_COLUMNS)  # valeur et présence de chaque signal
CONTEXT_SIZE = 18 + LIVE_SIZE + 2  # L maintenant, moyenne et dispersion sur 7 jours, heure
WINDOW = np.arange(-(CONTEXT_LENGTH - 1), 1)  # les 28 relevés qui finissent à l'instant t


def transform(theta: np.ndarray) -> np.ndarray:
    """Logarithme des signaux très étalés (pas, délais). Les données absentes restent NaN."""
    values = np.array(theta, dtype=np.float32, copy=True)
    values[..., LOG] = np.log1p(np.maximum(values[..., LOG], 0.0))
    return values


def global_normal(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Moyenne et dispersion de chaque signal sur tout le monde. `values` est déjà transformé."""
    flat = values.reshape(-1, values.shape[-1])
    mean = np.nanmean(flat, axis=0)
    spread = np.clip(np.nanstd(flat, axis=0), 1e-3, None)
    return mean.astype(np.float32), spread.astype(np.float32)


def person_normal(
    values: np.ndarray, global_mean: np.ndarray, global_spread: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """La normale de chaque personne, sur sa période de référence. `values` : [n, relevés, s]."""
    window = values[:, :REFERENCE_SNAPSHOTS]
    count = (~np.isnan(window)).sum(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # signal jamais relevé
        mean = np.nanmean(window, axis=1)
        spread = np.nanstd(window, axis=1)
    few = count < MIN_OBSERVATIONS
    mean = np.where(few, global_mean, mean)
    spread = np.where(few, global_spread, spread)
    # Une personne très régulière ne doit pas voir le moindre écart devenir énorme.
    spread = np.maximum(spread, 0.3 * global_spread)
    return mean.astype(np.float32), spread.astype(np.float32)


def encoder_inputs(
    values: np.ndarray,
    global_mean: np.ndarray,
    global_spread: np.ndarray,
    person_mean: np.ndarray,
    person_spread: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Les trois vues d'un relevé : `g`, `p` et `m`. `values` : [n, ..., s], normale : [n, s]."""
    present = ~np.isnan(values)
    shape = (len(values),) + (1,) * (values.ndim - 2) + (values.shape[-1],)
    g = np.clip((values - global_mean) / global_spread, -CLIP, CLIP)
    p = (values - person_mean.reshape(shape)) / person_spread.reshape(shape)
    p = np.clip(p, -CLIP, CLIP)
    g = np.where(present, g, 0.0).astype(np.float32)
    p = np.where(present, p, 0.0).astype(np.float32)
    return g, p, present.astype(np.float32)


def time_features(index: np.ndarray) -> np.ndarray:
    """Heure et jour de la semaine d'un relevé, à partir de son rang : [..., 4]."""
    index = np.asarray(index)
    hour = np.asarray(SNAPSHOT_HOURS)[index % SLOTS] / 24.0
    weekday = (index // SLOTS % 7) / 7.0
    turn = 2.0 * np.pi
    features = [np.sin(turn * hour), np.cos(turn * hour)]
    features += [np.sin(turn * weekday), np.cos(turn * weekday)]
    return np.stack(features, axis=-1).astype(np.float32)


def live_features(p: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Comportement en direct : les signaux de l'app et de la frappe d'un relevé : [..., 12]."""
    return np.concatenate([p[..., LIVE_COLUMNS], m[..., LIVE_COLUMNS]], axis=-1)


def context_features(states: np.ndarray, live: np.ndarray, slot: np.ndarray) -> np.ndarray:
    """Le contexte donné au réseau A. `states` : [n, 28, 6], les L des sept derniers jours."""
    hour = np.asarray(SNAPSHOT_HOURS)[np.asarray(slot)] / 24.0
    clock = np.stack([np.sin(2.0 * np.pi * hour), np.cos(2.0 * np.pi * hour)], axis=-1)
    parts = [states[:, -1], states.mean(axis=1), states.std(axis=1), live, clock]
    return np.concatenate(parts, axis=-1).astype(np.float32)
