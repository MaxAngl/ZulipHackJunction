"""Un relevé θ à partir des réponses brutes de Garmin Connect.

On garde les noms et l'ordre de `ml/simulation/spec.py` : un relevé de la vraie montre a la même
forme qu'un relevé simulé. Seuls les 19 signaux de la montre sont lus ici ; les trois signaux
« app » viennent du comportement dans l'app.

Garmin ne documente pas ces réponses : les champs lus viennent de la bibliothèque `garminconnect`
et de réponses observées. Un champ absent donne None, jamais une erreur.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from ml.simulation.spec import SIGNALS
from ml.watch import Reading

# Blocs mesurés par la montre ; les autres (app, frappe) viennent du comportement dans l'app.
WATCH_BLOCKS = ("instant", "day", "night", "daily")
WATCH_SIGNALS: tuple[str, ...] = tuple(s.name for s in SIGNALS if s.block in WATCH_BLOCKS)

__all__ = ["WATCH_SIGNALS", "Reading", "read_signals"]

# Les mesures instantanées sont moyennées sur la demi-heure qui précède la dernière mesure,
# à condition que celle-ci ne soit pas trop vieille (la montre se synchronise par à-coups).
INSTANT_WINDOW = timedelta(minutes=30)
MAX_STALENESS = timedelta(hours=3)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _first(source: dict[str, Any] | None, *keys: str) -> float | None:
    for key in keys:
        value = _number((source or {}).get(key))
        if value is not None:
            return value
    return None


def _recent_mean(pairs: Any, now: datetime) -> float | None:
    """Moyenne des paires [horodatage en ms GMT, valeur] de la dernière demi-heure mesurée.

    Garmin code une absence de mesure par une valeur négative (-1, -2) : on l'écarte.
    """
    points = []
    for pair in pairs or []:
        if not isinstance(pair, list | tuple) or len(pair) < 2:
            continue
        timestamp, value = _number(pair[0]), _number(pair[1])
        if timestamp is not None and value is not None and value >= 0:
            points.append((timestamp, value))
    if not points:
        return None
    last = datetime.fromtimestamp(max(ts for ts, _ in points) / 1000, UTC)
    if now - last > MAX_STALENESS:
        return None
    since = (last - INSTANT_WINDOW).timestamp() * 1000
    window = [value for ts, value in points if ts >= since]
    return sum(window) / len(window)


def _steps_last_hour(intervals: Any, now: datetime) -> float | None:
    """Pas de la dernière heure, à partir des tranches de 15 minutes déjà écoulées."""
    done = []
    for item in intervals or []:
        try:
            end = datetime.fromisoformat(item["endGMT"]).replace(tzinfo=UTC)
        except (KeyError, TypeError, ValueError):
            continue
        steps = _number(item.get("steps"))
        if end <= now and steps is not None:
            done.append((end, steps))
    if not done:
        return None
    last = max(end for end, _ in done)
    if now - last > MAX_STALENESS:
        return None
    return sum(steps for end, steps in done if end > last - timedelta(hours=1))


def _local_hour(timestamp_ms: float | None) -> float | None:
    """Heure locale d'un horodatage « Local » de Garmin (l'heure murale codée comme du GMT)."""
    if timestamp_ms is None:
        return None
    moment = datetime.fromtimestamp(timestamp_ms / 1000, UTC)
    return moment.hour + moment.minute / 60


def _outdoor_minutes(activities: Any) -> float | None:
    """Minutes des activités du jour enregistrées avec le GPS (la montre ne suit pas en continu)."""
    if activities is None:
        return None
    seconds = sum(
        _number(item.get("duration")) or 0.0
        for item in activities
        if item.get("startLatitude") is not None or item.get("hasPolyline")
    )
    return seconds / 60


def _minutes(seconds: float | None) -> float | None:
    return None if seconds is None else seconds / 60


def read_signals(raw: dict[str, Any], now: datetime) -> Reading:
    """Relevé θ (signaux de la montre) à l'instant `now`, qui doit avoir un fuseau."""
    summary = raw.get("summary") or {}
    sleep = raw.get("sleep") or {}
    night = sleep.get("dailySleepDTO") or {}
    scores = night.get("sleepScores") or {}
    hrv = (raw.get("hrv") or {}).get("hrvSummary") or {}

    sleep_seconds = _first(night, "sleepTimeSeconds")
    bedtime = _local_hour(_first(night, "sleepStartTimestampLocal"))
    moderate = _first(summary, "moderateIntensityMinutes")
    vigorous = _first(summary, "vigorousIntensityMinutes")
    intensity = None
    if moderate is not None or vigorous is not None:
        # Comme Garmin : une minute intense compte double.
        intensity = (moderate or 0.0) + 2 * (vigorous or 0.0)

    reading: Reading = {
        "heart_rate": _recent_mean((raw.get("heart_rates") or {}).get("heartRateValues"), now),
        "stress": _recent_mean((raw.get("stress") or {}).get("stressValuesArray"), now),
        # Le Body Battery bouge lentement : la dernière valeur du résumé du jour suffit.
        "body_battery": _first(summary, "bodyBatteryMostRecentValue"),
        "respiration": _recent_mean(
            (raw.get("respiration") or {}).get("respirationValuesArray"), now
        ),
        "steps_last_hour": _steps_last_hour(raw.get("steps"), now),
        "steps_today": _first(summary, "totalSteps"),
        "intensity_minutes_today": intensity,
        "floors_today": _first(summary, "floorsAscended"),
        "outdoor_minutes_today": _outdoor_minutes(raw.get("activities")),
        "sleep_hours": None if sleep_seconds is None else sleep_seconds / 3600,
        "sleep_score": _first(scores.get("overall"), "value"),
        "deep_sleep_minutes": _minutes(_first(night, "deepSleepSeconds")),
        "rem_sleep_minutes": _minutes(_first(night, "remSleepSeconds")),
        "awake_minutes": _minutes(_first(night, "awakeSleepSeconds")),
        "bedtime_hour": None if bedtime is None else (bedtime - 12) % 24,
        "wake_hour": _local_hour(_first(night, "sleepEndTimestampLocal")),
        "hrv_overnight_ms": _first(hrv, "lastNightAvg")
        or _first(sleep, "avgOvernightHrv")
        or _first(night, "avgSleepHRV"),
        "spo2_sleep": _first(night, "averageSpO2Value", "avgSpO2"),
        "resting_hr": _first(summary, "restingHeartRate"),
    }
    assert tuple(reading) == WATCH_SIGNALS
    return reading
