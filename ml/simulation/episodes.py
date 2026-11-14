"""Journal d'épisodes : une demande tirée dans une zone, la réaction, la récompense.

Deux façons de faire vivre les patients :

- `simulate` : les zones sont tirées au hasard. C'est l'étape 2 de l'entraînement
  (docs/modele.md, section 6) : le réseau A doit voir toutes sortes de demandes, bonnes et
  mauvaises.
- `simulate_policy` : une politique choisit les zones, jour après jour, en ne voyant que les
  relevés θ déjà faits. C'est ce qui sert à évaluer le réseau B, et à refaire un journal là où
  B va réellement.

Certains jours, un patient ne reçoit rien : ces jours montrent comment son état évolue tout seul.
"""

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ml.simulation import patient
from ml.simulation.people import PATIENT, People, observe
from ml.simulation.reward import distance, reward
from ml.simulation.spec import (
    AXES,
    CONTEXT_DAYS,
    INTERVAL_AXES,
    REWARD_DELAY_DAYS,
    SIGNALS,
    SNAPSHOT_HOURS,
)

REQUEST_RATE = 0.8  # probabilité qu'un patient reçoive une demande un jour donné

Zones = tuple[np.ndarray, np.ndarray, np.ndarray]  # bas [n, 5], haut [n, 5], plafond [n]


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


@dataclass(frozen=True)
class Moment:
    """Ce qu'une politique reçoit au moment de choisir les zones du jour."""

    day: int
    slot: np.ndarray  # [n] relevé de la journée auquel la demande part
    theta: np.ndarray  # [n, jours x 4, signaux] : à ne lire que jusqu'au relevé (day, slot)
    asked: np.ndarray  # [n] bool : qui reçoit une demande aujourd'hui
    hidden_state: np.ndarray  # [n, 6] vérité cachée, réservée à l'oracle
    rules: patient.Rules  # vérité cachée, réservée à l'oracle


class Policy(Protocol):
    """Choisit une zone par personne. `feedback` lui rapporte ce qui s'est passé ensuite."""

    def zones(self, moment: Moment) -> Zones: ...

    def feedback(self, moment: Moment, axes: np.ndarray, reaction: patient.Reaction) -> None: ...


# Centre des zones tirées au hasard, axe par axe : intérêts, concret, durée, échange, exposition.
# Les axes de coût sont tirés plus bas, sinon presque toutes les demandes seraient trop lourdes
# et le journal ne contiendrait presque aucune réponse.
ZONE_CENTER_LOW = np.array([0.15, 0.15, 0.08, 0.08, 0.08])
ZONE_CENTER_HIGH = np.array([0.85, 0.85, 0.65, 0.65, 0.65])
STARTUP_CAP_RANGE = (0.15, 0.80)


def _random_zones(rng: np.random.Generator, n: int) -> Zones:
    center = rng.uniform(ZONE_CENTER_LOW, ZONE_CENTER_HIGH, (n, INTERVAL_AXES))
    half_width = rng.uniform(0.10, 0.25, (n, INTERVAL_AXES))
    low = np.clip(center - half_width, 0.0, 1.0)
    high = np.clip(center + half_width, 0.0, 1.0)
    return low, high, rng.uniform(*STARTUP_CAP_RANGE, n)


class RandomZones:
    """La politique de référence : des zones au hasard, comme dans le journal d'entraînement."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rng = rng

    def zones(self, moment: Moment) -> Zones:
        return _random_zones(self.rng, len(moment.slot))

    def feedback(self, moment: Moment, axes: np.ndarray, reaction: patient.Reaction) -> None:
        return None


def _requests_in(
    rng: np.random.Generator, low: np.ndarray, high: np.ndarray, startup_cap: np.ndarray
) -> np.ndarray:
    axes = np.empty((len(low), len(AXES)))
    axes[:, :INTERVAL_AXES] = low + rng.random(low.shape) * (high - low)
    axes[:, INTERVAL_AXES] = rng.random(len(low)) * startup_cap
    return axes


def _rows(
    asked: np.ndarray,
    day: int,
    slot: np.ndarray,
    zones: Zones,
    axes: np.ndarray,
    reaction: patient.Reaction,
    distances: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> dict[str, np.ndarray]:
    """Les lignes du journal pour un jour : une par personne qui a reçu une demande."""
    low, high, startup_cap = zones
    d_before, d_after, d_expected = distances
    return {
        "person": np.flatnonzero(asked),
        "day": np.full(asked.sum(), day),
        "slot": slot[asked],
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


def _collect(rows: dict[str, list[np.ndarray]]) -> Episodes:
    return Episodes(**{name: np.concatenate(parts) for name, parts in rows.items()})


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
        zones = _random_zones(rng, n_people)
        axes = _requests_in(rng, *zones)
        reaction = patient.react(rng, rules, state[:, day], axes, people.traits["chattiness"])
        slot = rng.integers(0, len(SNAPSHOT_HOURS), n_people)

        tomorrow = natural[:, day + REWARD_DELAY_DAYS]
        expected = np.clip(tomorrow + patient.EFFECT_DECAY * boost, 0.0, 1.0)
        boost = patient.EFFECT_DECAY * boost + np.where(asked[:, None], reaction.effect, 0.0)
        after = np.clip(tomorrow + boost, 0.0, 1.0)
        distances = (
            distance(state[:, day], *l_ref),
            distance(after, *l_ref),
            distance(expected, *l_ref),
        )
        for name, values in _rows(asked, day, slot, zones, axes, reaction, distances).items():
            rows[name].append(values)

    state[:, n_days - 1] = np.clip(natural[:, n_days - 1] + boost, 0.0, 1.0)
    return state, _collect(rows)


def simulate_policy(
    rng: np.random.Generator,
    people: People,
    rules: patient.Rules,
    l_ref: tuple[np.ndarray, np.ndarray],
    policy: Policy,
) -> tuple[np.ndarray, np.ndarray, Episodes]:
    """Boucle fermée : chaque jour, on relève θ, puis la politique choisit les zones.

    Renvoie l'état réel [n, jours, 6], les relevés θ [n, jours x 4, signaux] et le journal.
    Les relevés des jours à venir valent NaN tant qu'ils n'ont pas eu lieu : une politique ne
    peut donc pas lire l'avenir.
    """
    natural = people.natural
    n_people, n_days, _ = natural.shape
    slots = len(SNAPSHOT_HOURS)
    is_patient = people.group == PATIENT
    state = natural.copy()
    boost = np.zeros((n_people, natural.shape[2]))
    theta = np.full((n_people, n_days * slots, len(SIGNALS)), np.nan, dtype=np.float32)
    rows: dict[str, list[np.ndarray]] = {name: [] for name in Episodes.__dataclass_fields__}

    for day in range(n_days):
        state[:, day] = np.clip(natural[:, day] + boost, 0.0, 1.0)
        theta[:, day * slots : (day + 1) * slots] = observe(rng, people, state[:, day : day + 1])
        if day >= n_days - REWARD_DELAY_DAYS:
            break
        asked = is_patient & (rng.random(n_people) < REQUEST_RATE) & (day >= CONTEXT_DAYS)
        slot = rng.integers(0, slots, n_people)
        moment = Moment(day, slot, theta, asked, state[:, day], rules)
        low, high, startup_cap = policy.zones(moment)
        zones = (np.clip(low, 0.0, 1.0), np.clip(high, 0.0, 1.0), np.clip(startup_cap, 0.0, 1.0))
        axes = _requests_in(rng, *zones)
        reaction = patient.react(rng, rules, state[:, day], axes, people.traits["chattiness"])
        policy.feedback(moment, axes, reaction)

        tomorrow = natural[:, day + REWARD_DELAY_DAYS]
        expected = np.clip(tomorrow + patient.EFFECT_DECAY * boost, 0.0, 1.0)
        boost = patient.EFFECT_DECAY * boost + np.where(asked[:, None], reaction.effect, 0.0)
        after = np.clip(tomorrow + boost, 0.0, 1.0)
        distances = (
            distance(state[:, day], *l_ref),
            distance(after, *l_ref),
            distance(expected, *l_ref),
        )
        for name, values in _rows(asked, day, slot, zones, axes, reaction, distances).items():
            rows[name].append(values)

    return state, theta, _collect(rows)
