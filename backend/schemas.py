"""CONTRAT D'API : source de vérité unique entre frontend/ et backend/.

Toute modification ici change contract/openapi.json et les types TS du front.
Procédure obligatoire : voir AGENTS.md, section « Contrat d'API ».
"""

from typing import Literal

from pydantic import BaseModel, Field

Stage = Literal["idle", "proposed", "held", "sent", "answered"]
Slot = Literal["best", "bridge", "explore"]
Provider = Literal["gemini", "offline"]
MessageSource = Literal["suggested", "edited", "real_need"]
PatientAction = Literal["helped", "ignored"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class Person(BaseModel):
    id: str
    name: str
    interests: list[str]


class InterestPair(BaseModel):
    patient_interest: str
    helper_interest: str


class FormatState(BaseModel):
    """Un format de la grille fixe, avec l'effort qu'il demande au patient."""

    key: str
    label: str
    effort: float = Field(ge=0, le=1)


class ZoneState(BaseModel):
    """Zone des demandes acceptables pour le patient, maintenant."""

    center: float = Field(description="Centre sur l'axe λ (0 = aidant, 1 = patient)")
    low: float
    high: float
    half_width: float = Field(description="Demi-largeur : l'incertitude du modèle")
    effort_max: float = Field(description="Effort maximal acceptable, entre 0 et 1")
    common_center: float = Field(description="Centre du modèle commun, avant correction")


class CandidateState(BaseModel):
    """Une demande générée, puis mesurée."""

    id: str
    text: str
    pair: InterestPair
    lam: float = Field(ge=0, le=1, description="Position mesurée sur l'axe λ")
    intended: float | None = Field(description="Position visée par le générateur")
    format: str
    format_label: str
    effort: float = Field(ge=0, le=1)
    in_zone: bool
    off_topic: bool
    slot: Slot | None = Field(description="Case occupée parmi les trois propositions")
    provider: Provider


class MessageState(BaseModel):
    """La demande envoyée par l'aidant, après mesure."""

    id: str
    text: str
    helper_id: str
    pair: InterestPair
    lam: float = Field(ge=0, le=1)
    format: str
    format_label: str
    effort: float = Field(ge=0, le=1)
    source: MessageSource
    status: Literal["delivered", "held"]
    hold_reason: str | None = Field(description="Pourquoi le message est retenu, s'il l'est")


class RoundState(BaseModel):
    number: int
    stage: Stage
    step: int = Field(ge=1, le=12, description="Étape courante de la boucle, de 1 à 12")
    helper_id: str | None
    pairs: list[InterestPair]
    candidates: list[CandidateState]
    message: MessageState | None


class HistoryEntry(BaseModel):
    number: int
    helper_name: str
    text: str
    lam: float
    effort: float
    format_label: str
    source: MessageSource
    action: PatientAction
    theta_before: float
    theta_expected: float
    theta_after: float
    reward: float = Field(description="θ après − θ attendu")
    center_before: float
    center_after: float = Field(description="Centre de la zone au même θ, après apprentissage")


class GeneratorState(BaseModel):
    provider: Provider
    model: str | None
    note: str


class ModelState(BaseModel):
    kind: Literal["simulated"] = "simulated"
    offset: float = Field(description="Correction personnelle du centre de la zone")
    observations: int


class LoopState(BaseModel):
    """Tout l'état de la démo : un patient, sa zone, la manche en cours et l'historique."""

    patient: Person
    helpers: list[Person]
    theta: float = Field(ge=0, le=1, description="État du patient (capteur simulé)")
    formats: list[FormatState]
    zone: ZoneState
    round: RoundState
    held: list[MessageState]
    history: list[HistoryEntry]
    generator: GeneratorState
    model: ModelState


class ThetaRequest(BaseModel):
    theta: float = Field(ge=0, le=1)


class SendRequest(BaseModel):
    """Choix de l'aidant : une proposition, une proposition modifiée, ou son propre texte."""

    proposal_id: str | None = None
    text: str | None = Field(default=None, max_length=600)


class RespondRequest(BaseModel):
    action: PatientAction


class ErrorDetail(BaseModel):
    code: str = Field(description="Identifiant machine en snake_case, ex. validation_error")
    message: str = Field(description="Message lisible par un humain")


class ErrorResponse(BaseModel):
    """Format unique de toutes les erreurs renvoyées par l'API."""

    error: ErrorDetail
