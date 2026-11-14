"""État provisoire : un seul nombre de 0 à 1 à partir d'un relevé de la montre.

L'app attend aujourd'hui un seul nombre `theta`, qui joue le rôle de L(θ) (docs/modele.md,
section 8). En attendant l'autoencodeur (#22), on inverse le générateur `ml/simulation/people.py`
pour une personne moyenne : chaque signal donne une estimation de sa composante (sommeil,
énergie, calme, activité), et l'état est la moyenne des composantes estimées.

Limite principale : sans historique, pas de normalisation par personne. Une fréquence cardiaque
de repos basse « de nature » remonte l'état, alors qu'elle ne dit rien de la personne.
"""

from dataclasses import dataclass

import numpy as np

from ml.simulation.people import BATTERY_DRAIN_BY_SLOT, DAY_SHARE_BY_SLOT
from ml.simulation.spec import SNAPSHOT_HOURS

# Un relevé : nom du signal (ml/simulation/spec.py) -> valeur, None si absente.
Reading = dict[str, float | None]

# Avant cette part de la journée, les cumuls (pas, étages...) sont trop petits pour dire
# quelque chose : on les ignore.
MIN_DAY_SHARE = 0.25


@dataclass(frozen=True)
class Rule:
    """Valeur du signal quand sa composante vaut 0,5, et variation quand elle gagne 1."""

    component: str
    center: float
    gain: float
    scale: str = "none"  # "day" : cumul de la journée ; "drain" : Body Battery qui se vide


# Coefficients repris de `observe` dans ml/simulation/people.py, traits à leur moyenne.
# Non utilisés : heart_rate et steps_last_hour (trop liés au mouvement du moment),
# outdoor_minutes_today (tout ou rien), et bedtime_hour et wake_hour : le rythme est la
# régularité des horaires, qu'une seule nuit ne mesure pas (coucher à minuit = rythme nul).
RULES: dict[str, Rule] = {
    "stress": Rule("calm", 45.0, -55.0),
    "respiration": Rule("calm", 15.0, -3.2),
    "hrv_overnight_ms": Rule("calm", 45.0, 27.0),
    "body_battery": Rule("energy", 55.0, 70.0, "drain"),
    "resting_hr": Rule("energy", 60.0, -15.0),
    "steps_today": Rule("activity", 7500.0, 9750.0, "day"),
    "intensity_minutes_today": Rule("activity", 25.0, 90.0, "day"),
    "floors_today": Rule("activity", 8.0, 16.0, "day"),
    "sleep_hours": Rule("sleep", 7.1, 1.5),
    "sleep_score": Rule("sleep", 58.0, 60.0),
    "deep_sleep_minutes": Rule("sleep", 70.0, 55.0),
    "rem_sleep_minutes": Rule("sleep", 95.0, 55.0),
    "awake_minutes": Rule("sleep", 35.0, -55.0),
    "spo2_sleep": Rule("sleep", 95.5, 1.2),
}


@dataclass(frozen=True)
class Estimate:
    components: dict[str, float]  # chaque composante estimée, de 0 à 1
    theta: float  # leur moyenne : le nombre envoyé à l'app


def _shift(rule: Rule, value: float, hour: float) -> float | None:
    """Écart de la composante à 0,5 selon ce signal, borné à ±0,5."""
    if rule.scale == "day":
        share = float(np.interp(hour, SNAPSHOT_HOURS, DAY_SHARE_BY_SLOT))
        if share < MIN_DAY_SHARE:
            return None
        value /= share
    elif rule.scale == "drain":
        value += 1.1 * float(np.interp(hour, SNAPSHOT_HOURS, BATTERY_DRAIN_BY_SLOT))
    return float(np.clip((value - rule.center) / rule.gain, -0.5, 0.5))


def estimate(reading: Reading, hour: float) -> Estimate:
    """État provisoire d'un relevé pris à `hour` (heure locale, décimale)."""
    shifts: dict[str, list[float]] = {}
    for name, rule in RULES.items():
        value = reading.get(name)
        if value is None:
            continue
        shift = _shift(rule, value, hour)
        if shift is not None:
            shifts.setdefault(rule.component, []).append(shift)
    if not shifts:
        raise ValueError("no usable watch signal in this reading")
    components = {name: 0.5 + sum(values) / len(values) for name, values in shifts.items()}
    return Estimate(components, sum(components.values()) / len(components))
