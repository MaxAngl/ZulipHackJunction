"""Application FastAPI. Lancer : uv run uvicorn backend.main:app --reload --port 8000"""

from typing import Any

from fastapi import FastAPI

from backend.errors import register_error_handlers
from backend.loop import loop
from backend.schemas import (
    ErrorResponse,
    HealthResponse,
    LoopState,
    RespondRequest,
    SendRequest,
    ThetaRequest,
)
from ml.model import load_env_file

# La clé Gemini vient de `.env` (jamais commité). Sans clé, la boucle tourne hors ligne.
load_env_file()

app = FastAPI(title="Needed API", version="0.2.0")
register_error_handlers(app)

# Documente le format d'erreur dans le contrat OpenAPI (et donc dans les types TS).
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/loop")
def get_loop() -> LoopState:
    """État complet de la boucle."""
    return loop.state()


@app.post("/api/loop/theta", responses=ERROR_RESPONSES)
def set_theta(body: ThetaRequest) -> LoopState:
    """Étape 1 : nouvelle mesure de l'état du patient (capteur simulé)."""
    return loop.set_theta(body.theta)


@app.post("/api/loop/propose", responses=ERROR_RESPONSES)
def propose() -> LoopState:
    """Étapes 2 à 6 : zone, paires, génération, mesure, trois propositions pour l'aidant."""
    return loop.propose()


@app.post("/api/loop/send", responses=ERROR_RESPONSES)
def send(body: SendRequest) -> LoopState:
    """Étapes 7 et 8 : l'aidant envoie une demande, qui est vérifiée avant d'être transmise."""
    return loop.send(body.proposal_id, body.text)


@app.post("/api/loop/skip", responses=ERROR_RESPONSES)
def skip() -> LoopState:
    """Étape 7 : l'aidant passe son tour."""
    return loop.skip()


@app.post("/api/loop/respond", responses=ERROR_RESPONSES)
def respond(body: RespondRequest) -> LoopState:
    """Étapes 9 à 12 : réponse du patient, nouvelle mesure, récompense, apprentissage."""
    return loop.respond(body.action)


@app.post("/api/loop/reset", responses=ERROR_RESPONSES)
def reset() -> LoopState:
    """Remet la démo à zéro."""
    return loop.reset()
