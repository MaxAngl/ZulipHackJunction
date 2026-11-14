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


def test_full_round_from_proposals_to_learning():
    state = _post("/api/loop/propose")
    proposals = _proposals(state)
    assert state.round.stage == "proposed"
    assert 1 <= len(proposals) <= 3
    assert all(candidate.in_zone for candidate in proposals)
    assert len({candidate.slot for candidate in proposals}) == len(proposals)

    state = _post("/api/loop/send", {"proposal_id": proposals[0].id})
    assert state.round.stage == "sent"
    assert state.round.message is not None
    assert state.round.message.status == "delivered"
    assert state.round.message.source == "suggested"

    state = _post("/api/loop/respond", {"action": "helped"})
    assert state.round.stage == "answered"
    assert state.model.observations == 1
    entry = state.history[-1]
    assert entry.reward == pytest.approx(entry.theta_after - entry.theta_expected, abs=1e-3)
    assert state.theta == entry.theta_after


def test_moving_theta_refilters_the_measured_requests():
    _post("/api/loop/propose")
    state = _post("/api/loop/theta", {"theta": 0.1})
    assert state.zone.center > 0.9
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
