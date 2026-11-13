"""Application FastAPI. Lancer : uv run uvicorn backend.main:app --reload --port 8000"""

from typing import Any

from fastapi import FastAPI

from backend.errors import register_error_handlers
from backend.schemas import ErrorResponse, HealthResponse, PredictRequest, PredictResponse
from ml.model import predict

app = FastAPI(title="Hackathon API", version="0.1.0")
register_error_handlers(app)

# Documente le format d'erreur dans le contrat OpenAPI (et donc dans les types TS).
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/api/predict", responses=ERROR_RESPONSES)
def predict_route(body: PredictRequest) -> PredictResponse:
    result = predict(body.text)
    return PredictResponse(label=result.label, score=result.score)
