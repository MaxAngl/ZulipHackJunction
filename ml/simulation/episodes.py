"""Journal d'épisodes : une demande tirée dans une zone au hasard, la réaction, la récompense.

C'est l'étape 2 de l'entraînement (docs/modele.md, section 6). Les zones sont tirées au hasard
pour que le réseau A voie toutes sortes de demandes, bonnes et mauvaises. Certains jours, un
patient ne reçoit rien : ces jours montrent comment son état évolue tout seul.
"""

from dataclasses import dataclass

import numpy as np

from ml.simulation import patient
from ml.simulation.people import PATIENT, People
from ml.simulation.reward import distance, reward
from ml.simulation.spec import AXES, CONTEXT_DAYS, INTERVAL_AXES, REWARD_DELAY_DAYS, SNAPSHOT_HOURS

REQUEST_RATE = 0.8  # probabilité qu'un patient reçoive une demande un jour donné


@dataclass(frozen=True)
class Episodes:
    """Une ligne par demande. `m` lignes au total."""

    person: np.ndarray  # [m] indice de la personne
    day: np.ndarray  # [m] jour de la demande
    slot: np.ndarray  # [m] relevé de la journée auquel elle est envoyée
    zone_low: np.ndarray  # [m, 5] bas de l'intervalle, pour les cinq axes à intervalle
    zone_high: np.ndarray  # [m, 5] haut de l'intervalle
    startup_cap: np.ndarray  # [m] plafond du coût de démarrage
    axes: np.ndarray  # [m, 6] position de la demande sur les axes
    replied: np.ndarray  # [m] bool
    delay_hours: np.ndarray  # [m] NaN sans réponse
    reply_length: np.ndarray  # [m] NaN sans réponse
    fit: np.ndarray  # [m] vérité cachée : proximité de ce qui convient au patient
    overload: np.ndarray  # [m] vérité cachée : dépassement de ce qu'il supporte
    d_before: np.ndarray  # [m] distance à L_ref avant la demande
    d_after: np.ndarray  # [m] distance à L_ref après le délai
    d_expected: np.ndarray  # [m] distance à L_ref qu'il aurait eue sans la demande
    reward: np.ndarray  # [m] récompense retenue : avant contre après
    reward_counterfactual: np.ndarray  # [m] variante : sans la demande contre après


# Centre des zones tirées au hasard, axe par axe : intérêts, concret, durée, échange, exposition.
# Les axes de coût sont tirés plus bas, sinon presque toutes les demandes seraient trop lourdes
# et le journal ne contiendrait presque aucune réponse.
ZONE_CENTER_LOW = np.array([0.15, 0.15, 0.08, 0.08, 0.08])
ZONE_CENTER_HIGH = np.array([0.85, 0.85, 0.65, 0.65, 0.65])
STARTUP_CAP_RANGE = (0.15, 0.80)


def _random_zones(rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    center = rng.uniform(ZONE_CENTER_LOW, ZONE_CENTER_HIGH, (n, INTERVAL_AXES))
    half_width = rng.uniform(0.10, 0.25, (n, INTERVAL_AXES))
    low = np.clip(center - half_width, 0.0, 1.0)
    high = np.clip(center + half_width, 0.0, 1.0)
    return low, high, rng.uniform(*STARTUP_CAP_RANGE, n)


def _requests_in(
    rng: np.random.Generator, low: np.ndarray, high: np.ndarray, startup_cap: np.ndarray
) -> np.ndarray:
    axes = np.empty((len(low), len(AXES)))
    axes[:, :INTERVAL_AXES] = low + rng.random(low.shape) * (high - low)
    axes[:, INTERVAL_AXES] = rng.random(len(low)) * startup_cap
    return axes


def simulate(
    rng: np.random.Generator,
    people: People,
    rules: patient.Rules,
    l_ref: tuple[np.ndarray, np.ndarray],
) -> tuple[np.ndarray, Episodes]:
    """Fait vivre les patients jour après jour. Renvoie l'état réel [n, jours, 6] et le journal."""
    natural = people.natural
    n_people, n_days, _ = natural.shape
    is_patient = people.group == PATIENT
    state = natural.copy()
    boost = np.zeros((n_people, natural.shape[2]))  # ce qui reste des demandes passées
    rows: dict[str, list[np.ndarray]] = {name: [] for name in Episodes.__dataclass_fields__}

    for day in range(n_days - REWARD_DELAY_DAYS):
        state[:, day] = np.clip(natural[:, day] + boost, 0.0, 1.0)
        asked = is_patient & (rng.random(n_people) < REQUEST_RATE) & (day >= CONTEXT_DAYS)
        low, high, startup_cap = _random_zones(rng, n_people)
        axes = _requests_in(rng, low, high, startup_cap)
        reaction = patient.react(rng, rules, state[:, day], axes, people.traits["chattiness"])

        tomorrow = natural[:, day + REWARD_DELAY_DAYS]
        expected = np.clip(tomorrow + patient.EFFECT_DECAY * boost, 0.0, 1.0)
        boost = patient.EFFECT_DECAY * boost + np.where(asked[:, None], reaction.effect, 0.0)
        after = np.clip(tomorrow + boost, 0.0, 1.0)

        d_before = distance(state[:, day], *l_ref)
        d_after, d_expected = distance(after, *l_ref), distance(expected, *l_ref)
        today = {
            "person": np.flatnonzero(asked),
            "day": np.full(asked.sum(), day),
            "slot": rng.integers(0, len(SNAPSHOT_HOURS), n_people)[asked],
            "zone_low": low[asked],
            "zone_high": high[asked],
            "startup_cap": startup_cap[asked],
            "axes": axes[asked],
            "replied": reaction.replied[asked],
            "delay_hours": reaction.delay_hours[asked],
            "reply_length": reaction.reply_length[asked],
            "fit": reaction.fit[asked],
            "overload": reaction.overload[asked],
            "d_before": d_before[asked],
            "d_after": d_after[asked],
            "d_expected": d_expected[asked],
            "reward": reward(d_before, d_after)[asked],
            "reward_counterfactual": reward(d_expected, d_after)[asked],
        }
        for name, values in today.items():
            rows[name].append(values)

    state[:, n_days - 1] = np.clip(natural[:, n_days - 1] + boost, 0.0, 1.0)
    return state, Episodes(**{name: np.concatenate(parts) for name, parts in rows.items()})
