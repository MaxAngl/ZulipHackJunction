"""CONTRAT D'API : source de vérité unique entre frontend/ et backend/.

Toute modification ici change contract/openapi.json et les types TS du front.
Procédure obligatoire : voir AGENTS.md, section « Contrat d'API ».
"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class PredictResponse(BaseModel):
    label: str
    score: float = Field(ge=0, le=1)


class ErrorDetail(BaseModel):
    code: str = Field(description="Identifiant machine en snake_case, ex. validation_error")
    message: str = Field(description="Message lisible par un humain")


class ErrorResponse(BaseModel):
    """Format unique de toutes les erreurs renvoyées par l'API."""

    error: ErrorDetail
