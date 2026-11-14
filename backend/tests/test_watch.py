"""Montre Garmin : liaison par code, mesures qui font bouger θ, demande traitée depuis la montre."""

import re

import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_community, get_watches
from backend.schemas import (
    HelperHome,
    PatientHome,
    SessionResponse,
    WatchHome,
    WatchPairing,
    WatchPairingStatus,
    WatchStatus,
)
from backend.watch import WATCH_REPLY

client = TestClient(app)

CALM_DAY = {
    "local_hour": 18.0,
    "heart_rate": 62,
    "stress": 15,
    "body_battery": 70,
    "respiration": 13,
    "steps_today": 9000,
    "intensity_minutes_today": 60,
    "floors_today": 14,
    "resting_hr": 52,
}
TENSE_DAY = {
    "local_hour": 18.0,
    "stress": 80,
    "body_battery": 10,
    "respiration": 18,
    "steps_today": 800,
    "intensity_minutes_today": 0,
    "floors_today": 0,
    "resting_hr": 72,
}


@pytest.fixture(autouse=True)
def empty_database(monkeypatch: pytest.MonkeyPatch) -> None:
    get_community.cache_clear()  # nouvelle base en mémoire pour chaque test
    get_watches.cache_clear()
    monkeypatch.setattr("backend.community.suggestion_seed", lambda: 1234)


def _join(role: str, name: str, interests: list[str]) -> dict[str, str]:
    response = client.post(
        "/api/app/join", json={"role": role, "name": name, "interests": interests}
    )
    assert response.status_code == 200, response.text
    return {"X-Needed-Token": SessionResponse.model_validate(response.json()).token}


def _pair() -> WatchPairing:
    response = client.post("/api/watch/pair")
    assert response.status_code == 200, response.text
    return WatchPairing.model_validate(response.json())


def _pairing_status(pairing: WatchPairing) -> WatchPairingStatus:
    response = client.get(f"/api/watch/pair/{pairing.pairing_id}")
    assert response.status_code == 200, response.text
    return WatchPairingStatus.model_validate(response.json())


def _link(patient: dict[str, str], code: str) -> WatchStatus:
    response = client.post("/api/app/patient/watch", json={"code": code}, headers=patient)
    assert response.status_code == 200, response.text
    return WatchStatus.model_validate(response.json())


def _linked_watch(patient: dict[str, str]) -> dict[str, str]:
    pairing = _pair()
    _link(patient, pairing.code)
    token = _pairing_status(pairing).token
    assert token is not None
    return {"X-Needed-Token": token}


def _sync(watch: dict[str, str], reading: dict) -> WatchHome:
    response = client.post("/api/watch/sync", json=reading, headers=watch)
    assert response.status_code == 200, response.text
    return WatchHome.model_validate(response.json())


def test_watch_links_with_the_code_it_shows() -> None:
    patient = _join("patient", "Aino", ["gardening"])
    pairing = _pair()
    assert re.fullmatch(r"\d{6}", pairing.code)
    assert _pairing_status(pairing).status == "waiting"

    status = _link(patient, pairing.code)

    assert status.linked and status.last_seen is None
    linked = _pairing_status(pairing)
    assert linked.status == "linked"
    assert linked.patient_name == "Aino"
    assert linked.token not in (None, patient["X-Needed-Token"])  # jeton propre à la montre


def test_wrong_code_is_refused() -> None:
    patient = _join("patient", "Aino", ["gardening"])
    wrong = f"{(int(_pair().code) + 1) % 1_000_000:06d}"

    response = client.post("/api/app/patient/watch", json={"code": wrong}, headers=patient)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "code_not_found"


def test_watch_readings_move_the_state() -> None:
    patient = _join("patient", "Aino", ["gardening"])
    watch = _linked_watch(patient)

    good = _sync(watch, CALM_DAY).theta
    bad = _sync(watch, TENSE_DAY).theta

    assert good > 0.6 > 0.4 > bad
    status = WatchStatus.model_validate(
        client.get("/api/app/patient/watch", headers=patient).json()
    )
    assert status.last_reading is not None and status.last_reading.stress == 80
    assert status.last_seen is not None
    assert status.theta == pytest.approx(bad)


def test_request_shows_on_the_watch_and_is_answered_there() -> None:
    patient = _join("patient", "Aino", ["Gardening", "jazz"])
    helper = _join("helper", "Mikko", ["cooking"])
    watch = _linked_watch(patient)
    home = HelperHome.model_validate(client.post("/api/app/helper/suggest", headers=helper).json())
    client.post("/api/app/helper/send", json={"proposal_id": home.proposals[0].id}, headers=helper)

    shown = _sync(watch, {"local_hour": 13.0})  # aucune mesure : θ ne bouge pas
    assert shown.request is not None and shown.request.from_name == "Mikko"

    response = client.post(
        "/api/watch/answer", json={"request_id": shown.request.id, "accept": True}, headers=watch
    )

    assert response.status_code == 200, response.text
    assert WatchHome.model_validate(response.json()).request is None
    past = PatientHome.model_validate(client.get("/api/app/patient", headers=patient).json()).past
    assert past[0].reply == WATCH_REPLY


def test_unlinked_watch_is_refused() -> None:
    patient = _join("patient", "Aino", ["gardening"])
    watch = _linked_watch(patient)

    status = WatchStatus.model_validate(
        client.delete("/api/app/patient/watch", headers=patient).json()
    )
    response = client.post("/api/watch/sync", json={"local_hour": 9.0}, headers=watch)

    assert not status.linked
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "watch_not_linked"
