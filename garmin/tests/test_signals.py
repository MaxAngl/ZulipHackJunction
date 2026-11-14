"""Lecture des réponses de Garmin Connect : formes observées, valeurs absentes, données périmées."""

from datetime import UTC, datetime, timedelta

import pytest

from garmin.signals import WATCH_SIGNALS, read_signals

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def minutes_ago(minutes: int) -> int:
    return ms(NOW - timedelta(minutes=minutes))


def quarter(end_minutes_ago: int, steps: int) -> dict:
    end = NOW - timedelta(minutes=end_minutes_ago)
    start = end - timedelta(minutes=15)
    return {
        "startGMT": start.strftime("%Y-%m-%dT%H:%M:%S.0"),
        "endGMT": end.strftime("%Y-%m-%dT%H:%M:%S.0"),
        "steps": steps,
    }


RAW = {
    "summary": {
        "totalSteps": 4200,
        "floorsAscended": 6.0,
        "moderateIntensityMinutes": 10,
        "vigorousIntensityMinutes": 5,
        "restingHeartRate": 58,
        "bodyBatteryMostRecentValue": 62,
    },
    "heart_rates": {
        "heartRateValues": [
            [minutes_ago(90), 100],  # hors de la demi-heure
            [minutes_ago(20), 70],
            [minutes_ago(10), None],
            [minutes_ago(5), 80],
        ]
    },
    "stress": {
        "stressValuesArray": [[minutes_ago(15), 30], [minutes_ago(5), -1], [minutes_ago(3), 40]]
    },
    "respiration": {"respirationValuesArray": [[minutes_ago(4), 14.0]]},
    "steps": [
        quarter(75, 999),  # plus d'une heure avant la dernière tranche
        quarter(45, 100),
        quarter(30, 200),
        quarter(15, 300),
        quarter(0, 400),
        quarter(-15, 0),  # tranche future, pas encore écoulée
    ],
    "sleep": {
        "dailySleepDTO": {
            "sleepTimeSeconds": 7 * 3600 + 1800,
            "deepSleepSeconds": 80 * 60,
            "remSleepSeconds": 100 * 60,
            "awakeSleepSeconds": 20 * 60,
            "sleepStartTimestampLocal": ms(datetime(2026, 11, 13, 23, 30, tzinfo=UTC)),
            "sleepEndTimestampLocal": ms(datetime(2026, 11, 14, 7, 15, tzinfo=UTC)),
            "averageSpO2Value": 96.0,
            "sleepScores": {"overall": {"value": 81, "qualifierKey": "GOOD"}},
        }
    },
    "hrv": {"hrvSummary": {"lastNightAvg": 52, "weeklyAvg": 50}},
    "activities": [
        {"duration": 1800.0, "startLatitude": 60.17},  # marche avec GPS
        {"duration": 3600.0, "startLatitude": None},  # séance en salle
    ],
}


def test_reads_every_watch_signal_in_the_spec_order() -> None:
    reading = read_signals(RAW, NOW)

    assert tuple(reading) == WATCH_SIGNALS
    assert reading["heart_rate"] == pytest.approx(75.0)
    assert reading["stress"] == pytest.approx(35.0)
    assert reading["respiration"] == pytest.approx(14.0)
    assert reading["body_battery"] == 62
    assert reading["steps_last_hour"] == 100 + 200 + 300 + 400
    assert reading["steps_today"] == 4200
    assert reading["intensity_minutes_today"] == 10 + 2 * 5
    assert reading["floors_today"] == 6
    assert reading["outdoor_minutes_today"] == pytest.approx(30.0)


def test_reads_last_night() -> None:
    reading = read_signals(RAW, NOW)

    assert reading["sleep_hours"] == pytest.approx(7.5)
    assert reading["sleep_score"] == 81
    assert reading["deep_sleep_minutes"] == 80
    assert reading["rem_sleep_minutes"] == 100
    assert reading["awake_minutes"] == 20
    assert reading["bedtime_hour"] == pytest.approx(11.5)  # 23 h 30, en heures après midi
    assert reading["wake_hour"] == pytest.approx(7.25)
    assert reading["hrv_overnight_ms"] == 52
    assert reading["spo2_sleep"] == 96


def test_missing_answers_give_none() -> None:
    reading = read_signals({"summary": None, "sleep": {}, "hrv": None}, NOW)

    assert tuple(reading) == WATCH_SIGNALS
    assert all(value is None for value in reading.values())


def test_stale_instant_data_is_dropped() -> None:
    later = NOW + timedelta(hours=4)

    reading = read_signals(RAW, later)

    assert reading["heart_rate"] is None
    assert reading["stress"] is None
    assert reading["steps_last_hour"] is None
    assert reading["steps_today"] == 4200  # les cumuls du jour restent valables
