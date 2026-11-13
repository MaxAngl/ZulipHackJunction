"""Garde-fou du contrat d'API : casse dès qu'un schéma change sans que l'équipe le sache."""

import json

from fastapi.testclient import TestClient

from backend.export_openapi import CONTRACT_PATH
from backend.main import app
from backend.schemas import ErrorResponse, HealthResponse, PredictResponse

client = TestClient(app)


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


def test_predict_returns_contract_shape():
    response = client.post("/api/predict", json={"text": "super projet"})
    assert response.status_code == 200
    body = PredictResponse.model_validate(response.json())
    assert 0.0 <= body.score <= 1.0


def test_invalid_input_returns_error_shape():
    response = client.post("/api/predict", json={"text": ""})
    assert response.status_code == 422
    body = ErrorResponse.model_validate(response.json())
    assert body.error.code == "validation_error"


def test_unknown_route_returns_error_shape():
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    ErrorResponse.model_validate(response.json())
