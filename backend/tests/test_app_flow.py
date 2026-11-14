"""La vraie app, de l'inscription au merci : deux personnes, une demande, une réponse."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.community import Community
from backend.main import app, get_community
from backend.schemas import (
    ErrorResponse,
    HelperHome,
    PatientHome,
    SessionResponse,
    SignupRequest,
)
from backend.store import Store
from backend.tests.accounts import account, signup_body
from ml.model import SIGNALS, request_axes

client = TestClient(app)


@pytest.fixture(autouse=True)
def empty_database(monkeypatch: pytest.MonkeyPatch) -> None:
    get_community.cache_clear()  # nouvelle base en mémoire pour chaque test
    # Les propositions ne dépendent plus de l'horloge : mêmes tirages à chaque lancement.
    monkeypatch.setattr("backend.community.suggestion_seed", lambda: 1234)
    # Le corps virtuel d'un patient dépend de son identifiant, tiré au hasard : on le fixe.
    monkeypatch.setattr("backend.community.body_seed", lambda _patient_id: 7)


def _join(role: str, name: str, interests: list[str]) -> dict[str, str]:
    response = client.post("/api/app/signup", json=signup_body(role, name, interests))
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
    community = get_community()
    store = community.store
    stored = store.patients()[0]
    waiting = next(r for r in store.requests_of("patient", stored.id) if r.status != "declined")
    zone = community._zone(stored)
    fits = zone.contains(waiting.lam, waiting.effort, request_axes(waiting.lam, waiting.format))
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


@pytest.mark.parametrize("released", [True, False])
def test_a_waiting_request_is_released_only_if_it_still_fits(released: bool):
    """Les positions sont fixées à la main : au cœur de la zone, ou tout à l'opposé."""
    community = Community(Store(":memory:"))
    patient = account(community.store, "patient", "Aino", ["gardening"])
    helper = account(community.store, "helper", "Mikko", ["cooking"])
    center = community._zone(patient).center
    current = _waiting_request(community.store, helper.id, patient.id, center, "delivered")
    lam = center if released else 0.05
    waiting = _waiting_request(community.store, helper.id, patient.id, lam, "held")

    community.decline(patient, current.id)

    # Un refus déplace peu la zone : une demande posée en son centre y est encore, une demande
    # tout près des intérêts de l'aidant n'y entre toujours pas.
    after = community.store.request(waiting.id)
    assert after is not None
    assert after.status == ("delivered" if released else "held")
    inbox = community.patient_home(community.store.user(patient.id)).inbox
    assert len(inbox) == (1 if released else 0)


def test_a_never_asked_patient_waits_from_their_sign_up(monkeypatch: pytest.MonkeyPatch):
    """Aino attend depuis sa dernière demande (t=150), Bob depuis son inscription (t=300).

    Mêmes intérêts pour les deux : seul le temps d'attente les départage.
    """
    now = {"t": 100.0}
    monkeypatch.setattr("backend.store.time.time", lambda: now["t"])
    community = Community(Store(":memory:"))
    aino = account(community.store, "patient", "Aino", ["gardening"])
    helper = account(community.store, "helper", "Mikko", ["cooking"])
    now["t"] = 150.0
    _waiting_request(community.store, helper.id, aino.id, 0.64, "answered")
    now["t"] = 300.0
    account(community.store, "patient", "Bob", ["gardening"])

    assert community.suggest(helper).patient_name == "Aino"


def test_each_helper_is_offered_the_patient_sharing_their_interests():
    _join("patient", "Aino", ["gardening"])
    _join("patient", "Bob", ["chess"])
    mikko = _join("helper", "Mikko", ["chess"])
    sara = _join("helper", "Sara", ["gardening"])

    assert _helper("/api/app/helper/suggest", mikko).patient_name == "Bob"
    assert _helper("/api/app/helper/suggest", sara).patient_name == "Aino"


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


def test_the_demo_entry_sets_the_level_and_the_networks_read_it_back():
    patient = _join("patient", "Aino", ["gardening"])
    community = get_community()
    before = community._zone(community.store.patients()[0])
    response = client.post("/api/app/patient/state", json={"theta": 0.2}, headers=patient)
    assert response.status_code == 200
    stored = community.store.patients()[0]
    assert stored.theta == pytest.approx(0.2, abs=0.1)  # lu sur les signaux, pas recopié
    assert stored.theta_source == "sensor"
    after = community._zone(stored)
    assert after.center > before.center  # il va plus mal : plus près de ses intérêts
    assert after.effort_max <= before.effort_max


def test_an_answer_is_scored_and_tunes_the_patient_vector(tmp_path: Path):
    community = Community(Store(tmp_path / "needed.db"))
    patient = account(community.store, "patient", "Aino", ["gardening"])
    helper = account(community.store, "helper", "Mikko", ["cooking"])
    home = community.suggest(helper)
    community.send(helper, home.proposals[0].id, None)
    request = community.store.requests_of("patient", patient.id)[0]
    community.reply(patient, request.id, "A long and careful answer. " * 5)

    after = community.store.user(patient.id)
    answered = community.store.request(request.id)
    assert after is not None and answered is not None
    assert after.theta_source == "wearable"
    assert after.zone_obs == 1
    assert after.tried_formats == [request.format]
    assert answered.theta_before is not None and answered.theta_after == after.theta
    assert answered.reward is not None and 0.0 <= answered.reward <= 100.0
    assert community._companion(after).vector.shape == (8,)


def test_typing_signals_measured_by_the_app_are_accepted():
    patient = _join("patient", "Aino", ["gardening"])
    helper = _join("helper", "Mikko", ["cooking"])
    home = _helper("/api/app/helper/suggest", helper)
    _helper("/api/app/helper/send", helper, {"proposal_id": home.proposals[0].id})
    request_id = _patient_home(patient).inbox[0].id
    typing = {
        "characters": 80,
        "corrections": 8,
        "open_delay_seconds": 240.0,
        "first_key_delay_seconds": 6.5,
    }
    response = client.post(
        "/api/app/patient/reply",
        json={"request_id": request_id, "text": "Basil first.", "typing": typing},
        headers=patient,
    )
    assert response.status_code == 200, response.text
    body = get_community()._companion(get_community().store.patients()[0]).body
    last = dict(zip([s.name for s in SIGNALS], body.theta[-1], strict=True))
    assert last["typing_correction_rate"] == pytest.approx(10.0)
    assert last["open_delay_minutes"] == pytest.approx(4.0)
    assert last["first_key_delay_seconds"] == pytest.approx(6.5)


def test_data_survives_a_restart(tmp_path: Path):
    path = tmp_path / "needed.db"
    first = Community(Store(path))
    session = first.signup(SignupRequest(**signup_body("patient", "Aino", ["gardening"])))

    second = Community(Store(path))
    assert second.signed_in(session.token).name == "Aino"


def test_what_the_networks_learned_about_a_patient_survives_a_restart(tmp_path: Path):
    """Rien du corps virtuel n'est enregistré : il se reconstruit en rejouant les demandes."""
    path = tmp_path / "needed.db"
    first = Community(Store(path))
    patient = account(first.store, "patient", "Aino", ["gardening"])
    helper = account(first.store, "helper", "Mikko", ["cooking"])
    for answer in ("Start with basil.", None):
        home = first.suggest(helper)
        first.send(helper, home.proposals[0].id, None)
        request = first.store.requests_of("patient", patient.id)[-1]
        if answer:
            first.reply(patient, request.id, answer)
        else:
            first.decline(patient, request.id)
    before = first._companion(patient)

    second = Community(Store(path))
    after = second._companion(patient)
    assert len(after.outcomes) == 2
    assert after.reading.wellbeing == pytest.approx(before.reading.wellbeing)
    assert after.vector == pytest.approx(before.vector, abs=1e-5)
    assert after.zone.center == pytest.approx(before.zone.center, abs=1e-4)
