"""Application FastAPI. Lancer : uv run uvicorn backend.main:app --reload --port 8000"""

import functools
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse

from backend.community import Community
from backend.errors import register_error_handlers
from backend.loop import loop
from backend.schemas import (
    AppUser,
    DeclineRequest,
    ErrorResponse,
    HealthResponse,
    HelperHome,
    JoinRequest,
    LoopState,
    PatientHome,
    ReplyRequest,
    RespondRequest,
    SendRequest,
    SessionResponse,
    ThanksRequest,
    ThetaRequest,
)
from backend.store import Store, User
from ml.model import load_env_file

# La clé Gemini vient de `.env` (jamais commité). Sans clé, la boucle tourne hors ligne.
load_env_file()

app = FastAPI(title="Needed API", version="0.3.0")
register_error_handlers(app)

# Documente le format d'erreur dans le contrat OpenAPI (et donc dans les types TS).
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse()


# --- Console de démo : un patient simulé, état en mémoire ---------------------------------


@app.get("/api/loop")
def get_loop() -> LoopState:
    """État complet de la boucle."""
    return loop.state()


@app.post("/api/loop/theta", responses=ERROR_RESPONSES)
def set_theta(body: ThetaRequest) -> LoopState:
    """Étape 1 : change l'état de fond du patient virtuel ; θ et L(θ) sont relus."""
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
    return loop.respond(body.action, body.typing)


@app.post("/api/loop/reset", responses=ERROR_RESPONSES)
def reset() -> LoopState:
    """Remet la démo à zéro."""
    return loop.reset()


# --- Vraie app : de vraies personnes, une base SQLite ---------------------------------------


@functools.cache
def get_community() -> Community:
    """Ouvre la base au premier appel, pas à l'import."""
    return Community(Store())


Token = Annotated[str | None, Header(alias="X-Needed-Token")]


def any_user(token: Token = None) -> User:
    return get_community().signed_in(token)


def helper_user(token: Token = None) -> User:
    return get_community().signed_in(token, "helper")


def patient_user(token: Token = None) -> User:
    return get_community().signed_in(token, "patient")


Helper = Annotated[User, Depends(helper_user)]
Patient = Annotated[User, Depends(patient_user)]


@app.post("/api/app/join", responses=ERROR_RESPONSES)
def join(body: JoinRequest) -> SessionResponse:
    """Inscription : un prénom, des centres d'intérêt, et un jeton pour cet appareil."""
    return get_community().join(body.role, body.name, body.interests)


@app.get("/api/app/me", responses=ERROR_RESPONSES)
def me(user: Annotated[User, Depends(any_user)]) -> AppUser:
    return AppUser(id=user.id, role=user.role, name=user.name, interests=user.interests)


@app.get("/api/app/helper", responses=ERROR_RESPONSES)
def helper_home(user: Helper) -> HelperHome:
    """Écran de l'aidant : ses propositions en cours et ses demandes envoyées."""
    return get_community().helper_home(user)


@app.post("/api/app/helper/suggest", responses=ERROR_RESPONSES)
def helper_suggest(user: Helper) -> HelperHome:
    """Étapes 2 à 6 pour un vrai patient : trois demandes à lui adresser."""
    return get_community().suggest(user)


@app.post("/api/app/helper/send", responses=ERROR_RESPONSES)
def helper_send(body: SendRequest, user: Helper) -> HelperHome:
    """Étapes 7 et 8 : l'aidant envoie une proposition, une version modifiée ou son texte."""
    return get_community().send(user, body.proposal_id, body.text)


@app.post("/api/app/helper/skip", responses=ERROR_RESPONSES)
def helper_skip(user: Helper) -> HelperHome:
    return get_community().skip(user)


@app.post("/api/app/helper/thanks", responses=ERROR_RESPONSES)
def helper_thanks(body: ThanksRequest, user: Helper) -> HelperHome:
    """L'aidant dit ce que la réponse lui a apporté : la preuve d'utilité pour le patient."""
    return get_community().thank(user, body.request_id, body.text)


@app.get("/api/app/patient", responses=ERROR_RESPONSES)
def patient_home(user: Patient) -> PatientHome:
    """Écran du patient : les demandes à traiter et celles auxquelles il a répondu."""
    return get_community().patient_home(user)


@app.post("/api/app/patient/reply", responses=ERROR_RESPONSES)
def patient_reply(body: ReplyRequest, user: Patient) -> PatientHome:
    """Étapes 9 à 12 : le patient répond, son état est relu, son vecteur s'ajuste."""
    return get_community().reply(user, body.request_id, body.text, body.typing)


@app.post("/api/app/patient/decline", responses=ERROR_RESPONSES)
def patient_decline(body: DeclineRequest, user: Patient) -> PatientHome:
    return get_community().decline(user, body.request_id)


@app.post("/api/app/patient/state", responses=ERROR_RESPONSES)
def patient_state(body: ThetaRequest, user: Patient) -> PatientHome:
    """Entrée de démonstration : fixe le niveau de fond du corps virtuel du patient."""
    return get_community().push_state(user, body.theta)


# --- Servir le frontend React buildé (mode production et déploiement en ligne) ---
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    icons_dir = FRONTEND_DIST / "icons"
    if icons_dir.is_dir():
        app.mount("/icons", StaticFiles(directory=icons_dir), name="icons")

    moomins_dir = FRONTEND_DIST / "moomins"
    if moomins_dir.is_dir():
        app.mount("/moomins", StaticFiles(directory=moomins_dir), name="moomins")

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise StarletteHTTPException(status_code=404, detail="Index not found")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        file_path = FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        index_file = FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise StarletteHTTPException(status_code=404, detail="Not Found")
