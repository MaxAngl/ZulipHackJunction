"""Comptes à mot de passe, fils de discussion, besoins des patients, portails, base de démo."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.community import Community
from backend.main import app, get_community
from backend.schemas import (
    AdminHome,
    AppUser,
    ClinicianHome,
    DemoAccount,
    ErrorResponse,
    HelperHome,
    SessionResponse,
    ThreadsResponse,
)
from backend.seed import PASSWORD as DEMO_PASSWORD
from backend.seed import seed
from backend.store import Store
from backend.tests.accounts import PASSWORD, signup_body
from backend.threads import Threads

client = TestClient(app)


@pytest.fixture(autouse=True)
def empty_database(monkeypatch: pytest.MonkeyPatch) -> None:
    get_community.cache_clear()
    monkeypatch.setattr("backend.community.suggestion_seed", lambda: 1234)
    monkeypatch.setattr("backend.community.body_seed", lambda _patient_id: 7)


def _signup(role: str, name: str, interests: list[str], **extra: object) -> dict[str, str]:
    response = client.post("/api/app/signup", json=signup_body(role, name, interests, **extra))
    assert response.status_code == 200, response.text
    return {"X-Needed-Token": SessionResponse.model_validate(response.json()).token}


def _error(response) -> str:
    return ErrorResponse.model_validate(response.json()).error.code


def _threads(headers: dict[str, str]) -> ThreadsResponse:
    response = client.get("/api/app/threads", headers=headers)
    assert response.status_code == 200, response.text
    return ThreadsResponse.model_validate(response.json())


def _write(headers: dict[str, str], thread_id: str, text: str) -> ThreadsResponse:
    response = client.post(
        f"/api/app/threads/{thread_id}/messages", json={"text": text}, headers=headers
    )
    assert response.status_code == 200, response.text
    return ThreadsResponse.model_validate(response.json())


def _send_first_proposal(helper: dict[str, str]) -> None:
    home = HelperHome.model_validate(client.post("/api/app/helper/suggest", headers=helper).json())
    response = client.post(
        "/api/app/helper/send", json={"proposal_id": home.proposals[0].id}, headers=helper
    )
    assert response.status_code == 200, response.text


# --- Comptes ---------------------------------------------------------------------------------


def test_sign_up_sign_out_and_sign_back_in_with_the_password():
    token = _signup("patient", "Aino", ["gardening"], last_name="Laine", city="Helsinki")
    me = AppUser.model_validate(client.get("/api/app/me", headers=token).json())
    assert (me.first_name, me.last_name, me.city, me.role) == (
        "Aino",
        "Laine",
        "Helsinki",
        "patient",
    )

    assert client.post("/api/app/logout", headers=token).status_code == 200
    assert _error(client.get("/api/app/me", headers=token)) == "not_signed_in"

    response = client.post(
        "/api/app/login", json={"email": "  AINO@test.demo ", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    session = SessionResponse.model_validate(response.json())
    assert session.user.id == me.id and session.token != token["X-Needed-Token"]


def test_a_wrong_password_and_a_taken_email_are_refused():
    _signup("helper", "Mikko", ["cooking"])
    response = client.post("/api/app/login", json={"email": "mikko@test.demo", "password": "nope"})
    assert response.status_code == 401 and _error(response) == "wrong_credentials"
    response = client.post("/api/app/login", json={"email": "who@test.demo", "password": "nope"})
    assert response.status_code == 401 and _error(response) == "wrong_credentials"

    response = client.post("/api/app/signup", json=signup_body("patient", "Mikko", ["jazz"]))
    assert response.status_code == 409 and _error(response) == "email_taken"
    short = signup_body("patient", "Bob", ["jazz"], password="123")
    assert client.post("/api/app/signup", json=short).status_code == 422


def test_the_password_is_never_stored_in_clear():
    _signup("helper", "Mikko", ["cooking"])
    stored = get_community().store.user_by_email("mikko@test.demo")
    assert stored is not None
    assert PASSWORD not in stored.password_hash
    assert stored.password_hash.startswith("pbkdf2_sha256$")


def test_the_profile_is_kept_server_side_and_a_private_one_shows_little():
    patient = _signup("patient", "Aino", ["gardening"], bio="Basil grower.")
    helper = _signup("helper", "Mikko", ["cooking"])
    response = client.patch(
        "/api/app/me",
        json={"city": "Espoo", "allow_profile_view": False, "passion_photos": ["/a.png"]},
        headers=patient,
    )
    assert response.status_code == 200, response.text
    assert AppUser.model_validate(response.json()).city == "Espoo"

    home = HelperHome.model_validate(client.post("/api/app/helper/suggest", headers=helper).json())
    assert home.patient is not None
    assert (home.patient.name, home.patient.visible) == ("Aino", False)
    assert (home.patient.city, home.patient.bio, home.patient.passion_photos) == ("", "", [])


@pytest.mark.parametrize(("bio", "chosen"), [("I play chess.", "Aino"), ("", "Bob")])
def test_an_interest_written_only_in_the_bio_counts_for_matching(bio: str, chosen: str):
    """Aino n'écrit « chess » que dans sa bio. Sans bio, Bob, inscrit avant elle, passe devant.

    Repris de la PR #35 (Adel), que l'inscription à mot de passe remplace.
    """
    _signup("patient", "Bob", ["cooking"])
    _signup("patient", "Aino", ["gardening"], bio=bio)
    mikko = _signup("helper", "Mikko", ["chess"])
    home = HelperHome.model_validate(client.post("/api/app/helper/suggest", headers=mikko).json())
    assert home.patient_name == chosen


# --- Fils de discussion ------------------------------------------------------------------------


def test_one_thread_from_the_request_to_the_thanks_and_beyond():
    patient = _signup("patient", "Aino", ["gardening"])
    helper = _signup("helper", "Mikko", ["cooking"])
    _send_first_proposal(helper)

    mine = _threads(helper).threads[0]
    assert (mine.status, mine.can_write, mine.peer and mine.peer.name) == (
        "on_its_way",
        False,
        "Aino",
    )
    response = client.post(
        f"/api/app/threads/{mine.id}/messages", json={"text": "Hello?"}, headers=helper
    )
    assert response.status_code == 409 and _error(response) == "not_yet"

    theirs = _threads(patient).threads[0]
    assert (theirs.id, theirs.status, theirs.can_write) == (mine.id, "to_answer", True)
    typing = {"characters": 30, "corrections": 2, "first_key_delay_seconds": 3.0}
    response = client.post(
        f"/api/app/threads/{mine.id}/messages",
        json={"text": "Basil first.", "typing": typing},
        headers=patient,
    )
    assert response.status_code == 200, response.text
    stored = get_community().store.request(mine.id)
    assert stored is not None and stored.status == "answered" and stored.reward is not None

    thread = _write(helper, mine.id, "Planted it, thank you!").threads[0]
    assert thread.thanked
    assert [m.kind for m in thread.messages] == ["request", "reply", "thanks"]
    thread = _write(helper, mine.id, "Now the mint?").threads[0]
    thread = _write(patient, mine.id, "Its own pot, always.").threads[0]
    assert [m.kind for m in thread.messages][-2:] == ["message", "message"]
    assert [m.mine for m in thread.messages] == [False, True, False, False, True]
    assert thread.messages[2].text == "Planted it, thank you!"


def test_a_patient_can_let_a_request_go_and_the_helper_cannot_tell():
    patient = _signup("patient", "Aino", ["gardening"])
    helper = _signup("helper", "Mikko", ["cooking"])
    _send_first_proposal(helper)
    thread = _threads(patient).threads[0]

    response = client.post(f"/api/app/threads/{thread.id}/decline", headers=patient)
    assert response.status_code == 200, response.text
    assert ThreadsResponse.model_validate(response.json()).threads == []
    assert _threads(helper).threads[0].status == "on_its_way"
    response = client.post(f"/api/app/threads/{thread.id}/decline", headers=helper)
    assert response.status_code == 403


def test_a_stranger_cannot_read_or_write_a_thread():
    _signup("patient", "Aino", ["gardening"])
    helper = _signup("helper", "Mikko", ["cooking"])
    stranger = _signup("helper", "Sara", ["photography"])
    _send_first_proposal(helper)
    thread_id = _threads(helper).threads[0].id
    assert _threads(stranger).threads == []
    response = client.post(
        f"/api/app/threads/{thread_id}/messages", json={"text": "Hi"}, headers=stranger
    )
    assert response.status_code == 404


# --- Portails ----------------------------------------------------------------------------------


def _staff(role: str, email: str) -> dict[str, str]:
    community = get_community()
    community.create_account(role=role, email=email, password=PASSWORD, first_name="Staff")
    response = client.post("/api/app/login", json={"email": email, "password": PASSWORD})
    return {"X-Needed-Token": SessionResponse.model_validate(response.json()).token}


def test_a_clinician_follows_only_their_patients_and_keeps_notes():
    patient = _signup("patient", "Aino", ["gardening"], clinician_email="Dr@Clinic.demo")
    _signup("patient", "Bob", ["jazz"], clinician_email="other@clinic.demo")
    helper = _signup("helper", "Mikko", ["cooking"])
    _send_first_proposal(helper)
    thread = _threads(patient).threads[0]
    _write(patient, thread.id, "Basil first.")

    clinician = _staff("clinician", "dr@clinic.demo")
    home = ClinicianHome.model_validate(client.get("/api/clinician", headers=clinician).json())
    assert [item.first_name for item in home.patients] == ["Aino"]
    followed = home.patients[0]
    assert (followed.answered, followed.waiting) == (1, 0)
    assert len(followed.trend) == 2 and 0 <= followed.wellbeing <= 1
    assert "Basil" not in client.get("/api/clinician", headers=clinician).text

    notes = {"mood": "Calm", "proud": "Sourdough", "loves": "Jazz"}
    response = client.put(
        f"/api/clinician/patients/{followed.id}/notes", json=notes, headers=clinician
    )
    assert response.status_code == 200, response.text
    saved = ClinicianHome.model_validate(response.json()).patients[0].notes
    assert saved is not None and saved.mood == "Calm"

    bob = get_community().store.user_by_email("bob@test.demo")
    assert bob is not None
    response = client.put(f"/api/clinician/patients/{bob.id}/notes", json=notes, headers=clinician)
    assert response.status_code == 404
    assert client.get("/api/clinician", headers=patient).status_code == 403


def test_the_admin_sees_the_community_and_handles_feedback():
    patient = _signup("patient", "Aino", ["gardening"])
    helper = _signup("helper", "Mikko", ["cooking"])
    _send_first_proposal(helper)
    client.post("/api/app/feedback", json={"category": "bug", "message": "Slow"}, headers=patient)
    client.post("/api/app/feedback", json={"category": "question", "message": "Who are you?"})

    admin = _staff("admin", "admin@test.demo")
    home = AdminHome.model_validate(client.get("/api/admin", headers=admin).json())
    assert {member.name for member in home.members} >= {"Aino", "Mikko", "Staff"}
    assert [(item.from_name, item.to_name) for item in home.exchanges] == [("Mikko", "Aino")]
    assert {(item.sender_name, item.sender_role) for item in home.feedback} == {
        ("Aino", "patient"),
        ("Visitor", "visitor"),
    }

    target = home.feedback[0].id
    response = client.post(f"/api/admin/feedback/{target}", json={"resolved": True}, headers=admin)
    assert response.status_code == 200, response.text
    assert next(
        i for i in AdminHome.model_validate(response.json()).feedback if i.id == target
    ).resolved
    assert client.get("/api/admin", headers=helper).status_code == 403


# --- Base ------------------------------------------------------------------------------------


def test_a_database_from_the_previous_schema_is_set_aside(tmp_path: Path):
    path = tmp_path / "needed.db"
    with sqlite3.connect(path) as old:
        old.execute("CREATE TABLE users (id TEXT PRIMARY KEY, token TEXT)")
    old.close()

    store = Store(path)
    assert store.users() == []
    store.close()
    assert len(list(tmp_path.glob("needed.v0-*.bak"))) == 1


def test_the_demo_accounts_sign_in_and_tell_a_story(tmp_path: Path):
    store = Store(tmp_path / "needed.db")
    people = seed(store)
    community = Community(store)
    threads = Threads(community)

    session = community.login("sofia@needed.demo", DEMO_PASSWORD)
    sofia = community.signed_in(session.token)
    assert [t.status for t in threads.for_user(sofia).threads] == ["to_answer"]
    elena_thread = threads.for_user(people["Elena"]).threads[0]
    assert (elena_thread.status, elena_thread.thanked) == ("answered", False)
    for email in ("clinic@needed.demo", "admin@needed.demo", "clara@needed.demo"):
        assert community.login(email, DEMO_PASSWORD).user.email == email


def test_quick_login_lists_the_demo_accounts_and_never_a_real_one():
    get_community().create_account(
        role="patient",
        email="aino@needed.demo",
        password=PASSWORD,
        first_name="Aino",
        city="Helsinki",
        interests=["gardening"],
    )
    _signup("helper", "Mikko", ["cooking"])

    response = client.get("/api/app/demo/accounts")
    assert response.status_code == 200, response.text
    accounts = [DemoAccount.model_validate(item) for item in response.json()]
    assert [(a.email, a.role, a.first_name, a.interests) for a in accounts] == [
        ("aino@needed.demo", "patient", "Aino", ["gardening"])
    ]
