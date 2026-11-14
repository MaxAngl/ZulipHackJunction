"""La vraie app, de l'inscription au merci : deux personnes, une demande, une réponse."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.community import Community
from backend.main import app, get_community
from backend.schemas import ErrorResponse, HelperHome, PatientHome, SessionResponse
from backend.store import Store

client = TestClient(app)


@pytest.fixture(autouse=True)
def empty_database() -> None:
    get_community.cache_clear()  # nouvelle base en mémoire pour chaque test


def _join(role: str, name: str, interests: list[str]) -> dict[str, str]:
    response = client.post(
        "/api/app/join", json={"role": role, "name": name, "interests": interests}
    )
    assert response.status_code == 200, response.text
    session = SessionResponse.model_validate(response.json())
    assert session.user.role == role
    return {"X-Needed-Token": session.token}


def _helper(path: str, headers: dict[str, str], body: dict | None = None) -> HelperHome:
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    return HelperHome.model_validate(response.json())


def _patient_home(headers: dict[str, str]) -> PatientHome:
    response = client.get("/api/app/patient", headers=headers)
    assert response.status_code == 200, response.text
    return PatientHome.model_validate(response.json())


def test_request_reply_and_thanks_between_two_people():
    patient = _join("patient", "Aino", ["Gardening", "jazz"])
    helper = _join("helper", "Mikko", ["cooking"])

    home = _helper("/api/app/helper/suggest", helper)
    assert home.patient_name == "Aino"
    assert 1 <= len(home.proposals) <= 3

    home = _helper("/api/app/helper/send", helper, {"proposal_id": home.proposals[0].id})
    assert home.proposals == []
    assert [request.status for request in home.requests] == ["on_its_way"]

    inbox = _patient_home(patient).inbox
    assert len(inbox) == 1
    assert inbox[0].with_name == "Mikko"
    assert inbox[0].status == "to_answer"

    response = client.post(
        "/api/app/patient/reply",
        json={"request_id": inbox[0].id, "text": "Start with basil, it forgives everything."},
        headers=patient,
    )
    assert response.status_code == 200, response.text
    after = PatientHome.model_validate(response.json())
    assert after.inbox == []
    assert after.past[0].reply == "Start with basil, it forgives everything."

    home = HelperHome.model_validate(client.get("/api/app/helper", headers=helper).json())
    assert home.requests[0].status == "answered"
    assert home.requests[0].reply == "Start with basil, it forgives everything."

    home = _helper(
        "/api/app/helper/thanks",
        helper,
        {"request_id": home.requests[0].id, "text": "Planted it this morning, thank you."},
    )
    assert _patient_home(patient).past[0].thanks == "Planted it this morning, thank you."


def test_a_patient_gets_one_request_at_a_time():
    patient = _join("patient", "Aino", ["gardening"])
    first = _join("helper", "Mikko", ["cooking"])
    second = _join("helper", "Sara", ["photography"])

    for helper in (first, second):
        home = _helper("/api/app/helper/suggest", helper)
        _helper("/api/app/helper/send", helper, {"proposal_id": home.proposals[0].id})

    inbox = _patient_home(patient).inbox
    assert len(inbox) == 1  # la seconde demande attend son tour
    assert inbox[0].with_name == "Mikko"

    client.post("/api/app/patient/decline", json={"request_id": inbox[0].id}, headers=patient)
    inbox = _patient_home(patient).inbox
    assert [request.with_name for request in inbox] == ["Sara"]

    # L'aidant dont la demande a été mise de côté ne voit aucune différence.
    home = HelperHome.model_validate(client.get("/api/app/helper", headers=first).json())
    assert home.requests[0].status == "on_its_way"


def test_an_unrelated_real_need_is_held_and_the_helper_cannot_tell():
    patient = _join("patient", "Aino", ["gardening"])
    helper = _join("helper", "Mikko", ["cooking"])
    _helper("/api/app/helper/suggest", helper)

    home = _helper(
        "/api/app/helper/send", helper, {"text": "Could we have a call about my tax return?"}
    )
    assert home.requests[0].status == "on_its_way"
    assert _patient_home(patient).inbox == []


def test_screens_are_protected():
    response = client.get("/api/app/helper")
    assert response.status_code == 401
    assert ErrorResponse.model_validate(response.json()).error.code == "not_signed_in"

    patient = _join("patient", "Aino", ["gardening"])
    response = client.get("/api/app/helper", headers=patient)
    assert response.status_code == 403
    assert ErrorResponse.model_validate(response.json()).error.code == "wrong_role"


def test_a_helper_alone_has_nobody_to_ask():
    helper = _join("helper", "Mikko", ["cooking"])
    response = client.post("/api/app/helper/suggest", headers=helper)
    assert response.status_code == 409
    assert ErrorResponse.model_validate(response.json()).error.code == "nobody_yet"


def test_a_sensor_can_push_the_patient_state():
    patient = _join("patient", "Aino", ["gardening"])
    response = client.post("/api/app/patient/state", json={"theta": 0.2}, headers=patient)
    assert response.status_code == 200
    stored = get_community().store.patients()[0]
    assert stored.theta == pytest.approx(0.2)
    assert stored.theta_source == "sensor"


def test_answers_move_the_estimated_state_and_the_zone(tmp_path: Path):
    community = Community(Store(tmp_path / "needed.db"))
    patient = community.store.add_user("patient", "Aino", ["gardening"], 0.6)
    helper = community.store.add_user("helper", "Mikko", ["cooking"], 0.6)
    home = community.suggest(helper)
    community.send(helper, home.proposals[0].id, None)
    request = community.store.requests_of("patient", patient.id)[0]
    community.reply(patient, request.id, "A long and careful answer. " * 5)

    after = community.store.user(patient.id)
    answered = community.store.request(request.id)
    assert after is not None and answered is not None
    assert after.theta > 0.6  # réponse rapide et longue : l'état estimé monte
    assert after.theta_source == "behaviour"
    assert after.zone_obs == 1
    assert answered.reward == pytest.approx(after.theta - 0.6)


def test_data_survives_a_restart(tmp_path: Path):
    path = tmp_path / "needed.db"
    first = Community(Store(path))
    session = first.join("patient", "Aino", ["gardening"])

    second = Community(Store(path))
    assert second.signed_in(session.token).name == "Aino"
