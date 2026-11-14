"""Patient simulé : comment il réagit à une demande, selon son état et ses règles cachées.

Chaque patient a ses propres règles, tirées au hasard : ce qu'il supporte sur chaque axe de
coût, et où se trouve ce qui lui convient sur les axes de préférence. Les réseaux ne voient
jamais ces règles : ils doivent les deviner à partir des réactions.

Les idées derrière les règles :
- ce qu'un patient supporte augmente avec son état (énergie, sommeil, calme, engagement) ;
- plus il va mal, plus ce qui lui convient est proche de ses intérêts, et concret ;
- une demande apporte d'autant plus qu'elle mobilise, tant qu'elle reste supportable ;
- au-delà de ce qu'il supporte, il répond moins, et la demande lui pèse.
"""

from dataclasses import dataclass

import numpy as np

from ml.simulation.spec import component_index

SWEET_SPOT_WIDTH = 0.22
EFFECT_DECAY = 0.75  # part d'un effet qui reste le lendemain

# Ce que chaque composante de l'état reçoit de l'effet d'une demande.
EFFECT_BY_COMPONENT = np.array([0.5, 0.5, 0.9, 0.9, 0.8, 1.6])
OVERLOAD_COST = 0.05
IGNORED_COST = 0.015

_SLEEP, _ENERGY = component_index("sleep"), component_index("energy")
_CALM, _ENGAGEMENT = component_index("calm"), component_index("engagement")


@dataclass(frozen=True)
class Rules:
    """Règles cachées de chaque patient. Axes de coût : durée, échange, exposition, démarrage."""

    cap_base: np.ndarray  # [n, 4] ce qu'il supporte quand son état est au plus bas
    cap_slope: np.ndarray  # [n, 4] ce que son état y ajoute
    interest_slope: np.ndarray  # [n] à quel point il s'éloigne de ses intérêts quand il va bien
    concrete_slope: np.ndarray  # [n] à quel point il accepte l'abstrait quand il va bien
    gain: np.ndarray  # [n] ce qu'une demande bien choisie lui apporte


@dataclass(frozen=True)
class Reaction:
    replied: np.ndarray  # [n] bool
    delay_hours: np.ndarray  # [n] NaN s'il n'a pas répondu
    reply_length: np.ndarray  # [n] NaN s'il n'a pas répondu
    effect: np.ndarray  # [n, 6] ce que la demande ajoute à son état
    fit: np.ndarray  # [n] entre 0 et 1 : proximité de ce qui lui convient
    overload: np.ndarray  # [n] dépassement total de ce qu'il supporte


def draw_rules(rng: np.random.Generator, n_people: int) -> Rules:
    return Rules(
        cap_base=rng.uniform(0.10, 0.30, (n_people, 4)),
        cap_slope=rng.uniform(0.50, 0.90, (n_people, 4)),
        interest_slope=rng.uniform(0.30, 0.80, n_people),
        concrete_slope=rng.uniform(0.20, 0.70, n_people),
        gain=rng.uniform(0.04, 0.10, n_people),
    )


def capacities(rules: Rules, state: np.ndarray) -> np.ndarray:
    """Ce que chaque patient supporte aujourd'hui sur les quatre axes de coût : [n, 4]."""
    drivers = np.stack(
        [
            (state[:, _ENERGY] + state[:, _SLEEP]) / 2.0,  # durée
            state[:, _ENGAGEMENT],  # échange humain
            state[:, _CALM],  # exposition personnelle
            state[:, _ENERGY],  # coût de démarrage
        ],
        axis=1,
    )
    return np.clip(rules.cap_base + rules.cap_slope * drivers, 0.05, 1.0)


def sweet_spots(rules: Rules, state: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Position idéale sur les axes « intérêts » et « concret », selon l'état global."""
    wellbeing = state.mean(axis=1)
    interest = np.clip(1.0 - rules.interest_slope * wellbeing, 0.0, 1.0)
    concrete = np.clip(0.95 - rules.concrete_slope * wellbeing, 0.0, 1.0)
    return interest, concrete


def react(
    rng: np.random.Generator,
    rules: Rules,
    state: np.ndarray,
    axes: np.ndarray,
    chattiness: np.ndarray,
) -> Reaction:
    """Réaction de chaque patient à la demande placée en `axes` : [n, 6] dans l'ordre de AXES."""
    n_people = len(state)
    costs, cap = axes[:, 2:6], capacities(rules, state)
    interest, concrete = sweet_spots(rules, state)
    gap = (axes[:, 0] - interest) ** 2 + (axes[:, 1] - concrete) ** 2
    fit = np.exp(-gap / (2.0 * SWEET_SPOT_WIDTH**2))
    overload = np.clip(costs - cap, 0.0, None).sum(axis=1)
    # La dose : à quel point la demande mobilise le patient, dans la limite de ce qu'il supporte.
    dose = (np.minimum(costs[:, :3], cap[:, :3]) / cap[:, :3]).mean(axis=1)

    engagement, energy = state[:, _ENGAGEMENT], state[:, _ENERGY]
    urge = (
        1.6
        + 2.5 * (fit - 0.5)
        - 7.0 * overload
        - 1.5 * axes[:, 5] * (1.0 - energy)
        + 2.0 * (engagement - 0.5)
    )
    replied = rng.random(n_people) < 1.0 / (1.0 + np.exp(-urge))

    typical_delay = np.log(1.0 + 9.0 * (1.0 - engagement))
    delay = np.exp(rng.normal(typical_delay, 0.5)) * (1.0 + 2.0 * overload)
    length = chattiness * (0.5 + axes[:, 3]) * (0.6 + 0.8 * engagement) + rng.normal(
        0.0, 12.0, n_people
    )

    helped = rules.gain * fit * (0.3 + 0.7 * dose) - OVERLOAD_COST * overload
    ignored = -IGNORED_COST * (1.0 + 3.0 * overload)
    size = np.where(replied, helped, ignored)
    return Reaction(
        replied=replied,
        delay_hours=np.where(replied, np.clip(delay, 0.05, 48.0), np.nan),
        reply_length=np.where(replied, np.clip(length, 5.0, None), np.nan),
        effect=size[:, None] * EFFECT_BY_COMPONENT,
        fit=fit,
        overload=overload,
    )
