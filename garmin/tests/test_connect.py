"""Appels à Garmin Connect (faux client) : réponse manquante, repli sur la nuit de la veille."""

from datetime import date
from typing import Any

from garminconnect import GarminConnectNotFoundError

from garmin.connect import fetch_raw

TODAY, YESTERDAY = "2026-11-14", "2026-11-13"


class FakeGarmin:
    def __init__(self, nights: dict[str, int]) -> None:
        self.nights = nights  # date -> secondes de sommeil enregistrées

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        seconds = self.nights.get(cdate)
        return {"dailySleepDTO": {"calendarDate": cdate, "sleepTimeSeconds": seconds}}

    def get_hrv_data(self, cdate: str) -> dict[str, Any]:
        return {"hrvSummary": {"calendarDate": cdate, "lastNightAvg": 50}}

    def get_user_summary(self, cdate: str) -> dict[str, Any]:
        raise GarminConnectNotFoundError("no summary")

    def __getattr__(self, name: str) -> Any:
        return lambda *args: None


def test_keeps_tonight_when_recorded() -> None:
    raw = fetch_raw(FakeGarmin({TODAY: 25000, YESTERDAY: 27000}), date(2026, 11, 14))

    assert raw["sleep"]["dailySleepDTO"]["calendarDate"] == TODAY
    assert raw["hrv"]["hrvSummary"]["calendarDate"] == TODAY


def test_falls_back_to_the_night_before() -> None:
    raw = fetch_raw(FakeGarmin({YESTERDAY: 27000}), date(2026, 11, 14))

    assert raw["sleep"]["dailySleepDTO"]["calendarDate"] == YESTERDAY
    assert raw["hrv"]["hrvSummary"]["calendarDate"] == YESTERDAY


def test_missing_answer_gives_none() -> None:
    raw = fetch_raw(FakeGarmin({}), date(2026, 11, 14))

    assert raw["summary"] is None
    assert raw["sleep"]["dailySleepDTO"]["calendarDate"] == TODAY  # pas de nuit la veille non plus
