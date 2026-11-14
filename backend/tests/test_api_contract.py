"""Garde-fou du contrat d'API : casse dès qu'un schéma change sans que l'équipe le sache."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.export_openapi import CONTRACT_PATH
from backend.main import app
from backend.schemas import ErrorResponse, HealthResponse, LoopState

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_loop() -> None:
    client.post("/api/loop/reset")


def _post(path: str, body: dict | None = None) -> LoopState:
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    return LoopState.model_validate(response.json())


def _proposals(state: LoopState) -> list:
    return [candidate for candidate in state.round.candidates if candidate.slot is not None]


def test_openapi_matches_committed_contract():
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert app.openapi() == committed, (
        "Le schéma de l'API ne correspond plus à contract/openapi.json. "
        "Si le changement est voulu : `uv run python -m backend.export_openapi`, "
        "puis `npm --prefix frontend run gen:api`, puis prévenir l'équipe (AGENTS.md)."
    )


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    HealthResponse.model_validate(response.json())


def test_loop_starts_idle():
    response = client.get("/api/loop")
    assert response.status_code == 200
    state = LoopState.model_validate(response.json())
    assert state.round.stage == "idle"
    assert state.round.step == 1
    assert state.zone.low <= state.zone.center <= state.zone.high


def test_the_state_and_the_zone_come_from_the_networks():
    state = LoopState.model_validate(client.get("/api/loop").json())
    assert [component.key for component in state.state] == [
        "sleep",
        "rhythm",
        "energy",
        "calm",
        "activity",
        "engagement",
    ]
    assert len(state.signals) == 25
    assert {signal.modality for signal in state.signals} == {"watch", "app", "touch"}
    assert [axis.kind for axis in state.zone.axes] == ["interval"] * 5 + ["ceiling"]
    assert state.model.kind == "networks" and state.model.parameters > 0
    assert state.model.vector == [0.0] * 8  # aucun vécu : le modèle général
    assert state.distance > 1.0  # un patient est loin de la référence saine


def test_full_round_from_proposals_to_learning():
    state = _post("/api/loop/propose")
    proposals = _proposals(state)
    assert state.round.stage == "proposed"
    assert 1 <= len(proposals) <= 3
    assert all(candidate.in_zone for candidate in proposals)
    assert all(len(candidate.axes) == 6 for candidate in proposals)
    assert len({candidate.slot for candidate in proposals}) == len(proposals)

    state = _post("/api/loop/send", {"proposal_id": proposals[0].id})
    assert state.round.stage == "sent"
    assert state.round.message is not None
    assert state.round.message.status == "delivered"
    assert state.round.message.source == "suggested"

    typing = {"characters": 120, "corrections": 30, "first_key_delay_seconds": 12.0}
    state = _post("/api/loop/respond", {"action": "helped", "typing": typing})
    assert state.round.stage == "answered"
    assert state.model.observations == 1
    assert len(state.model.vector) == 8
    entry = state.history[-1]
    assert 0.0 <= entry.reward <= 100.0  # 50 = l'état n'a pas bougé
    assert state.theta == entry.theta_after
    # La frappe relevée pendant la réponse est entrée dans θ : 30 corrections sur 120 caractères.
    measured = {signal.name: signal.value for signal in state.signals}
    assert measured["typing_correction_rate"] == pytest.approx(25.0)
    assert measured["first_key_delay_seconds"] == pytest.approx(12.0)


def test_moving_the_hidden_level_moves_the_state_and_the_zone():
    low = _post("/api/loop/theta", {"theta": 0.2})
    high = _post("/api/loop/theta", {"theta": 0.85})
    assert low.level == pytest.approx(0.2) and high.level == pytest.approx(0.85)
    assert low.theta < high.theta  # les réseaux retrouvent le niveau à partir des signaux
    assert low.zone.center > high.zone.center + 0.1  # plus mal : plus près de ses intérêts
    assert low.zone.effort_max < high.zone.effort_max  # plus mal : demande plus légère


def test_moving_theta_refilters_the_measured_requests():
    _post("/api/loop/propose")
    state = _post("/api/loop/theta", {"theta": 0.1})
    assert all(candidate.in_zone for candidate in _proposals(state))


def test_out_of_zone_message_is_held_not_refused():
    _post("/api/loop/propose")
    state = _post("/api/loop/send", {"text": "Could we have a call about my tax return?"})
    assert state.round.stage == "held"
    assert state.round.message is not None
    assert state.round.message.status == "held"
    assert state.round.message.source == "real_need"
    assert state.round.message.hold_reason
    assert len(state.held) == 1

    response = client.post("/api/loop/respond", json={"action": "helped"})
    assert response.status_code == 409
    assert ErrorResponse.model_validate(response.json()).error.code == "no_message"


def test_unsafe_message_is_rejected():
    _post("/api/loop/propose")
    response = client.post("/api/loop/send", json={"text": "Could you lend me some money?"})
    assert response.status_code == 422
    assert ErrorResponse.model_validate(response.json()).error.code == "message_rejected"


def test_invalid_input_returns_error_shape():
    response = client.post("/api/loop/theta", json={"theta": 2})
    assert response.status_code == 422
    body = ErrorResponse.model_validate(response.json())
    assert body.error.code == "validation_error"


def test_unknown_route_returns_error_shape():
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    ErrorResponse.model_validate(response.json())
