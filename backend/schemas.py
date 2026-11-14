"""CONTRAT D'API : source de vérité unique entre frontend/ et backend/.

Toute modification ici change contract/openapi.json et les types TS du front.
Procédure obligatoire : voir AGENTS.md, section « Contrat d'API ».
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Role = Literal["helper", "patient"]
Interest = Annotated[str, Field(min_length=1, max_length=40)]
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


class AxisState(BaseModel):
    """Ce que la zone permet sur l'un des six axes d'une demande."""

    key: str
    label: str
    low: float = Field(description="Borne basse : un objectif, jamais une obligation")
    high: float = Field(description="Borne haute : sur un axe de coût, jamais dépassée")
    kind: Literal["interval", "ceiling"]


class ZoneState(BaseModel):
    """Zone des demandes acceptables pour le patient, maintenant."""

    center: float = Field(description="Centre sur l'axe λ (0 = aidant, 1 = patient)")
    low: float
    high: float
    half_width: float = Field(description="Demi-largeur de l'intervalle sur l'axe λ")
    effort_max: float = Field(description="Effort du format le plus lourd que la zone permet")
    common_center: float = Field(description="Centre du modèle général, sans vecteur personnel")
    axes: list[AxisState] = Field(
        default_factory=list, description="La zone sur les six axes, sortie par le réseau B"
    )


class ComponentState(BaseModel):
    """Une des six composantes de l'état L(θ) du patient."""

    key: str
    label: str
    value: float = Field(ge=0, le=1)
    reference: float = Field(description="Moyenne des personnes saines : L_ref")


class SignalState(BaseModel):
    """Un des signaux bruts de θ, au dernier relevé."""

    name: str
    unit: str
    modality: str = Field(description="watch, app ou touch")
    value: float | None = Field(description="Absente si le signal n'a pas été relevé")


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
    axes: list[float] = Field(default_factory=list, description="Position sur les six axes")


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
    axes: list[float] = Field(default_factory=list, description="Position sur les six axes")


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
    theta_before: float = Field(description="Moyenne de L(θ) avant la demande")
    theta_expected: float = Field(description="Obsolète : égal à theta_before")
    theta_after: float = Field(description="Moyenne de L(θ) vingt-quatre heures après")
    reward: float = Field(
        description="De 0 à 100 : le patient s'est-il rapproché de L_ref ? 50 = rien n'a changé"
    )
    center_before: float
    center_after: float = Field(description="Centre de la zone au même état, après apprentissage")
    fit: float | None = Field(
        default=None, description="Vérité cachée du patient virtuel : la demande lui convenait-elle"
    )
    overload: float | None = Field(
        default=None, description="Vérité cachée : de combien elle dépassait ce qu'il supporte"
    )


class GeneratorState(BaseModel):
    provider: Provider
    model: str | None
    note: str


class ModelState(BaseModel):
    kind: Literal["simulated", "networks"] = "networks"
    offset: float = Field(description="Écart entre le centre de la zone et celui du modèle général")
    observations: int
    parameters: int = Field(default=0, description="Nombre de paramètres des trois réseaux")
    vector: list[float] = Field(
        default_factory=list, description="Vecteur personnel du patient : 8 nombres"
    )


class LoopState(BaseModel):
    """Tout l'état de la démo : un patient, sa zone, la manche en cours et l'historique."""

    patient: Person
    helpers: list[Person]
    theta: float = Field(ge=0, le=1, description="Moyenne des six composantes de L(θ)")
    level: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Niveau de fond caché du patient virtuel, réglé par le curseur de la démo",
    )
    state: list[ComponentState] = Field(
        default_factory=list, description="L(θ) : l'état lu par l'autoencodeur"
    )
    distance: float = Field(default=0.0, description="Distance de L(θ) à L_ref")
    signals: list[SignalState] = Field(
        default_factory=list, description="θ : les 25 signaux bruts du dernier relevé"
    )
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


class TypingSignals(BaseModel):
    """Ce que l'app relève pendant que le patient écrit sa réponse.

    Des durées et des comptes, jamais les caractères tapés. Ce sont les trois signaux de frappe
    de θ (docs/modele.md, section 11).
    """

    characters: int = Field(ge=0, description="Caractères tapés, effacements compris")
    corrections: int = Field(ge=0, description="Nombre d'effacements")
    open_delay_seconds: float | None = Field(
        default=None, ge=0, description="Entre l'arrivée de la demande et son ouverture"
    )
    first_key_delay_seconds: float | None = Field(
        default=None, ge=0, description="Entre l'ouverture et la première touche"
    )


class RespondRequest(BaseModel):
    action: PatientAction
    typing: TypingSignals | None = None


# --- La vraie app : comptes, demandes et réponses entre de vraies personnes ---------------


class JoinRequest(BaseModel):
    role: Role
    name: str = Field(min_length=1, max_length=40)
    interests: list[Interest] = Field(min_length=1, max_length=8)


class AppUser(BaseModel):
    id: str
    role: Role
    name: str
    interests: list[str]


class SessionResponse(BaseModel):
    """Le jeton identifie l'appareil. Il est renvoyé dans l'en-tête `X-Needed-Token`."""

    token: str
    user: AppUser


class AppProposal(BaseModel):
    """Une demande proposée à l'aidant. Ni position, ni effort : il ne voit que le texte."""

    id: str
    text: str
    patient_interest: str
    helper_interest: str


class AppRequest(BaseModel):
    """Une demande, vue par l'aidant ou par le patient."""

    id: str
    text: str
    with_name: str = Field(description="Prénom de l'autre personne")
    status: Literal["on_its_way", "to_answer", "answered"]
    reply: str | None
    thanks: str | None
    created_at: float


class HelperHome(BaseModel):
    user: AppUser
    patient_name: str | None = Field(description="La personne à qui s'adressent les propositions")
    proposals: list[AppProposal]
    requests: list[AppRequest]


class PatientHome(BaseModel):
    user: AppUser
    inbox: list[AppRequest]
    past: list[AppRequest]


class ReplyRequest(BaseModel):
    request_id: str
    text: str = Field(min_length=1, max_length=1000)
    typing: TypingSignals | None = None


class DeclineRequest(BaseModel):
    request_id: str


class ThanksRequest(BaseModel):
    request_id: str
    text: str = Field(min_length=1, max_length=300)


# --- Montre Garmin (app Connect IQ) ---------------------------------------------------------


class WatchPairing(BaseModel):
    """La montre demande à être liée : elle affiche le code, le patient le saisit dans l'app."""

    pairing_id: str
    code: str = Field(description="Six chiffres, à saisir dans l'écran patient")
    expires_in: int = Field(description="Secondes avant que le code ne soit plus valable")


class WatchPairingStatus(BaseModel):
    status: Literal["waiting", "linked", "expired"]
    token: str | None = Field(description="Jeton de la montre, une fois liée")
    patient_name: str | None


class WatchLinkRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class WatchReading(BaseModel):
    """Mesures du moment envoyées par la montre. Noms de ml/simulation/spec.py ; absente = null."""

    local_hour: float = Field(ge=0, lt=24, description="Heure locale de la montre, décimale")
    heart_rate: float | None = None
    stress: float | None = None
    body_battery: float | None = None
    respiration: float | None = None
    steps_today: float | None = None
    intensity_minutes_today: float | None = None
    floors_today: float | None = None
    resting_hr: float | None = None


class WatchStatus(BaseModel):
    """Ce que l'écran patient montre de sa montre."""

    linked: bool
    linked_at: float | None
    last_seen: float | None
    last_reading: WatchReading | None
    theta: float = Field(ge=0, le=1, description="État du patient tel que l'app l'estime")


class WatchRequest(BaseModel):
    id: str
    text: str
    from_name: str


class WatchHome(BaseModel):
    """Ce que la montre affiche : l'état estimé et la demande à traiter, s'il y en a une."""

    name: str
    theta: float = Field(ge=0, le=1)
    request: WatchRequest | None


class WatchAnswer(BaseModel):
    request_id: str
    accept: bool


class ErrorDetail(BaseModel):
    code: str = Field(description="Identifiant machine en snake_case, ex. validation_error")
    message: str = Field(description="Message lisible par un humain")


class ErrorResponse(BaseModel):
    """Format unique de toutes les erreurs renvoyées par l'API."""

    error: ErrorDetail
