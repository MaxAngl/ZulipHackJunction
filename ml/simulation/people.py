"""Générateur d'états : des personnes simulées, leur état caché jour par jour, et leurs relevés θ.

Deux étages, comme dans la vraie vie :
- un état caché à six composantes, qui évolue lentement et que personne n'observe ;
- des signaux bruts θ, qui en découlent à travers les habitudes propres à chaque personne
  (son besoin de sommeil, sa fréquence cardiaque de repos...), avec du bruit et des trous.

Les habitudes ne dépendent pas de l'état : c'est ce qui oblige à normaliser θ par personne.
"""

from dataclasses import dataclass

import numpy as np

from ml.simulation.spec import (
    COMPONENTS,
    SIGNALS,
    SNAPSHOT_HOURS,
    component_index,
    signal_index,
)

HEALTHY, PATIENT = 0, 1
COURSES: tuple[str, ...] = ("stable", "relapse", "recovery")
COURSE_ODDS = (0.5, 0.3, 0.2)  # parmi les patients ; une personne saine est toujours stable

# Niveau moyen de l'état, par groupe. C'est l'hypothèse centrale du générateur.
SET_POINT = {HEALTHY: (0.78, 0.05), PATIENT: (0.52, 0.09)}
RELAPSE_DROP, RECOVERY_RISE, DRIFT_DAYS = 0.22, 0.15, 21

# Effets de l'heure du relevé (8 h, 13 h, 18 h, 22 h).
HR_BY_SLOT = np.array([8.0, 14.0, 12.0, 4.0])
STRESS_BY_SLOT = np.array([-5.0, 6.0, 3.0, -8.0])
BATTERY_DRAIN_BY_SLOT = np.array([0.0, 14.0, 26.0, 34.0])
DAY_SHARE_BY_SLOT = np.array([0.08, 0.42, 0.78, 1.0])  # part de la journée déjà écoulée
MOVEMENT_BY_SLOT = np.array([0.6, 1.0, 1.1, 0.4])

assert len(SNAPSHOT_HOURS) == len(DAY_SHARE_BY_SLOT)


@dataclass(frozen=True)
class People:
    group: np.ndarray  # [n] 0 = sain, 1 = patient
    course: np.ndarray  # [n] indice dans COURSES
    natural: np.ndarray  # [n, jours, 6] état caché en l'absence de toute demande
    traits: dict[str, np.ndarray]  # habitudes de chaque personne, indépendantes de son état


def _ar1(rng: np.random.Generator, shape: tuple[int, ...], rho: float, sigma: float) -> np.ndarray:
    """Bruit corrélé d'un jour à l'autre, le long de l'axe 1."""
    noise = rng.normal(0.0, sigma, shape)
    series = np.empty(shape)
    series[:, 0] = noise[:, 0] / np.sqrt(1.0 - rho**2)
    for day in range(1, shape[1]):
        series[:, day] = rho * series[:, day - 1] + noise[:, day]
    return series


def _drift(rng: np.random.Generator, course: np.ndarray, n_days: int) -> np.ndarray:
    """Rechute ou rétablissement : une pente de trois semaines, à partir d'un jour au hasard."""
    start = rng.uniform(0.2, 0.6, course.shape) * n_days
    progress = np.clip((np.arange(n_days)[None, :] - start[:, None]) / DRIFT_DAYS, 0.0, 1.0)
    size = np.select([course == 1, course == 2], [-RELAPSE_DROP, RECOVERY_RISE], default=0.0)
    return size[:, None] * progress


def draw_people(
    rng: np.random.Generator, n_people: int, n_days: int, healthy_share: float
) -> People:
    group = (rng.random(n_people) >= healthy_share).astype(np.int8)
    course = np.where(
        group == PATIENT, rng.choice(len(COURSES), n_people, p=COURSE_ODDS), 0
    ).astype(np.int8)

    mean = np.where(group == PATIENT, SET_POINT[PATIENT][0], SET_POINT[HEALTHY][0])
    spread = np.where(group == PATIENT, SET_POINT[PATIENT][1], SET_POINT[HEALTHY][1])
    set_point = np.clip(rng.normal(mean[:, None], spread[:, None], (n_people, 6)), 0.15, 0.95)

    # Une part commune à toutes les composantes (la personne va globalement mieux ou moins
    # bien), une part propre à chacune, et la pente éventuelle d'une rechute.
    shared = _ar1(rng, (n_people, n_days), rho=0.9, sigma=0.03)
    own = _ar1(rng, (n_people, n_days, 6), rho=0.7, sigma=0.03)
    drift = _drift(rng, course, n_days)
    natural = set_point[:, None, :] + shared[:, :, None] + drift[:, :, None] + own

    traits = {
        "sleep_need": rng.normal(7.5, 0.6, n_people),
        "chronotype": rng.normal(11.2, 0.8, n_people),  # heure du coucher, en heures après midi
        "resting_hr": rng.normal(60.0, 7.0, n_people),
        "hrv": np.exp(rng.normal(np.log(45.0), 0.35, n_people)),
        "steps": np.clip(rng.normal(7500.0, 2000.0, n_people), 2500.0, None),
        "chattiness": np.clip(rng.normal(120.0, 40.0, n_people), 30.0, None),
        "spo2_enabled": rng.random(n_people) < 0.5,
        "night_wear": rng.uniform(0.80, 0.98, n_people),
        "day_wear": rng.uniform(0.90, 0.99, n_people),
    }
    # Habitudes de frappe. Elles sont tirées d'un générateur à part : les tirages du générateur
    # principal ne bougent pas, donc tout le reste du jeu reste identique pour une même graine.
    touch = rng.spawn(1)[0]
    traits |= {
        "correction_habit": np.exp(touch.normal(np.log(9.0), 0.35, n_people)),  # pour 100 car.
        "open_habit": np.exp(touch.normal(np.log(18.0), 0.6, n_people)),  # minutes
        "first_key_habit": np.exp(touch.normal(np.log(8.0), 0.4, n_people)),  # secondes
        "typing_days": touch.uniform(0.5, 0.9, n_people),  # part des jours où elle écrit
    }
    return People(group, course, np.clip(natural, 0.02, 0.98), traits)


def _cumulative(total: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Répartit un total journalier sur les quatre relevés, sans jamais redescendre."""
    wobble = rng.normal(1.0, 0.06, (*total.shape, len(DAY_SHARE_BY_SLOT)))
    return np.maximum.accumulate(total[..., None] * DAY_SHARE_BY_SLOT * wobble, axis=-1)


def observe(rng: np.random.Generator, people: People, state: np.ndarray) -> np.ndarray:
    """Relevés θ pour chaque personne, jour et heure : [n, jours x 4, signaux], NaN = absente.

    `state` peut ne couvrir qu'un seul jour : c'est ce que fait la simulation en boucle fermée.
    """
    n_people, n_days, _ = state.shape
    touch = rng.spawn(1)[0]  # frappe : générateur à part, voir draw_people
    slots = len(SNAPSHOT_HOURS)
    traits = people.traits
    centered = {name: state[:, :, component_index(name)] - 0.5 for name in COMPONENTS}
    sleep, rhythm, energy = centered["sleep"], centered["rhythm"], centered["energy"]
    calm, activity, engagement = centered["calm"], centered["activity"], centered["engagement"]

    def per_day(scale: float) -> np.ndarray:
        return rng.normal(0.0, scale, (n_people, n_days))

    def per_slot(scale: float) -> np.ndarray:
        return rng.normal(0.0, scale, (n_people, n_days, slots))

    def trait(name: str) -> np.ndarray:
        return traits[name][:, None]

    # --- Dernière nuit et valeur du jour : identiques aux quatre relevés de la journée ---
    sleep_hours = trait("sleep_need") - 0.4 + 1.5 * sleep + per_day(0.45)
    awake = 35.0 - 55.0 * sleep + per_day(9.0)
    irregular = 0.25 + 1.4 * (0.5 - rhythm)  # moins le rythme tient, plus l'heure du coucher varie
    bedtime = trait("chronotype") - 1.6 * rhythm + per_day(1.0) * irregular
    resting_hr = trait("resting_hr") - 9.0 * energy - 6.0 * calm + per_day(1.8)
    daily = {
        "sleep_hours": sleep_hours,
        "sleep_score": 58.0 + 60.0 * sleep + per_day(6.0),
        "deep_sleep_minutes": 70.0 + 55.0 * sleep + per_day(12.0),
        "rem_sleep_minutes": 95.0 + 55.0 * sleep + per_day(15.0),
        "awake_minutes": awake,
        "bedtime_hour": bedtime,
        "wake_hour": (bedtime + 12.0 + sleep_hours + awake / 60.0) % 24.0,
        "hrv_overnight_ms": trait("hrv") * (1.0 + 0.6 * calm) + per_day(4.0),
        "spo2_sleep": 95.5 + 1.2 * sleep + per_day(0.7),
        "resting_hr": resting_hr,
        "reply_rate_7d": 0.55 + 0.9 * engagement + per_day(0.07),
        "reply_delay_hours_7d": 6.0 - 10.0 * engagement + per_day(1.2),
        "reply_length_7d": trait("chattiness") * (1.0 + 0.9 * engagement) + per_day(14.0),
    }

    def touch_noise(scale: float) -> np.ndarray:
        return touch.lognormal(0.0, scale, (n_people, n_days))

    # Frappe et réactivité : l'habitude de la personne, ralentie ou dégradée quand elle va mal.
    # Un patient typique corrige, tarde à ouvrir et hésite environ 1,7 fois plus qu'une
    # personne saine, avec beaucoup de variation d'un jour à l'autre.
    daily |= {
        "typing_correction_rate": trait("correction_habit")
        * np.exp(-1.4 * sleep - 0.7 * calm)
        * touch_noise(0.25),
        "open_delay_minutes": trait("open_habit") * np.exp(-2.4 * engagement) * touch_noise(0.5),
        "first_key_delay_seconds": trait("first_key_habit")
        * np.exp(-2.0 * energy)
        * touch_noise(0.35),
    }

    # --- Mesures instantanées et cumuls de la journée : une valeur par relevé ---
    level = np.clip(1.0 + 1.3 * activity, 0.15, None)  # niveau d'activité du jour
    steps_last_hour = (
        (trait("steps") * level / 13.0)[..., None]
        * MOVEMENT_BY_SLOT
        * rng.lognormal(0.0, 0.35, (n_people, n_days, slots))
    )
    went_out = rng.random((n_people, n_days)) < np.clip(0.6 + 0.9 * activity, 0.05, 0.98)
    outdoor = went_out * np.clip(35.0 + 80.0 * activity + per_day(15.0), 0.0, None)
    drain = BATTERY_DRAIN_BY_SLOT * (1.1 - 0.6 * calm)[..., None]
    by_slot = {
        "heart_rate": resting_hr[..., None] + HR_BY_SLOT + 0.004 * steps_last_hour + per_slot(5.0),
        "stress": (45.0 - 55.0 * calm)[..., None] + STRESS_BY_SLOT + per_slot(8.0),
        "body_battery": (55.0 + 70.0 * energy + 22.0 * sleep)[..., None] - drain + per_slot(6.0),
        "respiration": (15.0 - 3.2 * calm)[..., None] + per_slot(0.9),
        "steps_last_hour": steps_last_hour,
        "steps_today": _cumulative(
            trait("steps") * level * rng.lognormal(0.0, 0.2, (n_people, n_days)), rng
        ),
        "intensity_minutes_today": _cumulative(
            np.clip(25.0 + 90.0 * activity + per_day(10.0), 0.0, None), rng
        ),
        "floors_today": _cumulative(np.clip(8.0 + 16.0 * activity + per_day(3.0), 0.0, None), rng),
        "outdoor_minutes_today": _cumulative(outdoor, rng),
    }

    theta = np.empty((n_people, n_days, slots, len(SIGNALS)))
    for index, signal in enumerate(SIGNALS):
        values = by_slot[signal.name] if signal.name in by_slot else daily[signal.name][..., None]
        theta[..., index] = np.clip(values, signal.low, signal.high)
    for name in _WHOLE_NUMBERS:
        theta[..., signal_index(name)] = np.round(theta[..., signal_index(name)])

    _punch_holes(rng, touch, people, theta)
    return theta.reshape(n_people, n_days * slots, len(SIGNALS)).astype(np.float32)


def _punch_holes(
    rng: np.random.Generator, touch: np.random.Generator, people: People, theta: np.ndarray
) -> None:
    """Données absentes : montre non portée le jour ou la nuit, SpO2 désactivée, mesures perdues."""
    n_people, n_days, slots, _ = theta.shape
    traits = people.traits
    block = {name: [i for i, s in enumerate(SIGNALS) if s.block == name] for name in _BLOCKS}

    day_off = rng.random((n_people, n_days)) > traits["day_wear"][:, None]
    night_off = rng.random((n_people, n_days)) > traits["night_wear"][:, None]
    app_off = rng.random((n_people, n_days)) < 0.08  # aucune demande récente
    lost = rng.random((n_people, n_days, slots, len(block["instant"]))) < 0.03

    for index in block["instant"] + block["day"] + block["daily"]:
        theta[..., index][day_off] = np.nan
    for index in block["night"]:
        theta[..., index][night_off] = np.nan
    for index in block["app"]:
        theta[..., index][app_off] = np.nan
    # La frappe n'existe que les jours où la personne a écrit dans l'app.
    no_typing = app_off | (touch.random((n_people, n_days)) > traits["typing_days"][:, None])
    for index in block["touch"]:
        theta[..., index][no_typing] = np.nan
    for position, index in enumerate(block["instant"]):
        theta[..., index][lost[..., position]] = np.nan
    theta[~traits["spo2_enabled"], :, :, signal_index("spo2_sleep")] = np.nan


_BLOCKS = ("instant", "day", "night", "daily", "app", "touch")
_WHOLE_NUMBERS = (
    "heart_rate",
    "stress",
    "body_battery",
    "steps_last_hour",
    "steps_today",
    "intensity_minutes_today",
    "floors_today",
    "outdoor_minutes_today",
    "sleep_score",
    "deep_sleep_minutes",
    "rem_sleep_minutes",
    "awake_minutes",
    "spo2_sleep",
    "resting_hr",
    "reply_length_7d",
)
