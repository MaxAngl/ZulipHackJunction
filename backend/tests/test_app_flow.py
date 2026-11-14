"""La vraie app, de l'inscription au merci : deux personnes, une demande, une réponse."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.community import Community
from backend.main import app, get_community
from backend.schemas import ErrorResponse, HelperHome, PatientHome, SessionResponse
from backend.store import Store
from ml.model import ZoneParams, zone_for

client = TestClient(app)


@pytest.fixture(autouse=True)
def empty_database(monkeypatch: pytest.MonkeyPatch) -> None:
    get_community.cache_clear()  # nouvelle base en mémoire pour chaque test
    # Les propositions ne dépendent plus de l'horloge : mêmes tirages à chaque lancement.
    monkeypatch.setattr("backend.community.suggestion_seed", lambda: 1234)


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

    # Le patient est libre. La demande en attente part si elle entre encore dans sa zone, qui a
    # bougé puisqu'il vient de mettre une demande de côté. Sinon elle reste retenue.
    store = get_community().store
    stored = store.patients()[0]
    waiting = next(r for r in store.requests_of("patient", stored.id) if r.status != "declined")
    zone = zone_for(stored.theta, ZoneParams(stored.zone_offset, stored.zone_obs))
    fits = zone.contains(waiting.lam, waiting.effort)
    assert waiting.status == ("delivered" if fits else "held")
    inbox = _patient_home(patient).inbox
    assert [request.with_name for request in inbox] == (["Sara"] if fits else [])

    # Mise de côté, retenue ou transmise : aucun des deux aidants ne voit de différence.
    for helper in (first, second):
        home = HelperHome.model_validate(client.get("/api/app/helper", headers=helper).json())
        assert home.requests[0].status == "on_its_way"


def _waiting_request(store: Store, helper_id: str, patient_id: str, lam: float, status: str):
    return store.add_request(
        helper_id=helper_id,
        patient_id=patient_id,
        text="A small favour",
        patient_interest="gardening",
        helper_interest="cooking",
        lam=lam,
        format="opinion",
        effort=0.15,
        source="suggested",
        status=status,
        hold_reason=None if status == "delivered" else "busy",
        delivered_at=None,
    )


@pytest.mark.parametrize(("lam", "released"), [(0.64, True), (0.30, False)])
def test_a_waiting_request_is_released_only_if_it_still_fits(lam: float, released: bool):
    """Sans aucun tirage : les positions sont fixées à la main, le résultat est certain."""
    community = Community(Store(":memory:"))
    patient = community.store.add_user("patient", "Aino", ["gardening"], 0.6)
    helper = community.store.add_user("helper", "Mikko", ["cooking"], 0.6)
    current = _waiting_request(community.store, helper.id, patient.id, 0.64, "delivered")
    waiting = _waiting_request(community.store, helper.id, patient.id, lam, "held")

    community.decline(patient, current.id)

    # Après ce refus, l'état estimé passe de 0,60 à 0,51 et la zone couvre λ de 0,55 à 0,84.
    after = community.store.request(waiting.id)
    assert after is not None
    assert after.status == ("delivered" if released else "held")
    inbox = community.patient_home(community.store.user(patient.id)).inbox
    assert len(inbox) == (1 if released else 0)


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
