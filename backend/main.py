"""Application FastAPI. Lancer : uv run uvicorn backend.main:app --reload --port 8000"""

import functools
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse

from backend import portals
from backend.community import Community
from backend.errors import ApiError, register_error_handlers
from backend.loop import loop
from backend.schemas import (
    Ack,
    AdminHome,
    AppUser,
    ClinicianHome,
    ClinicianNotes,
    DeclineRequest,
    DemoAccount,
    ErrorResponse,
    FeedbackRequest,
    HealthResponse,
    HelperHome,
    LoginRequest,
    LoopState,
    MessageRequest,
    PatientHome,
    ProfileUpdate,
    ReplyRequest,
    ResolveRequest,
    RespondRequest,
    SendRequest,
    SessionResponse,
    SignupRequest,
    ThanksRequest,
    ThetaRequest,
    ThreadsResponse,
    WatchAnswer,
    WatchHome,
    WatchLinkRequest,
    WatchPairing,
    WatchPairingStatus,
    WatchReading,
    WatchStatus,
)
from backend.store import Store, User
from backend.threads import Threads
from backend.views import app_user
from backend.watch import WatchDevice, Watches
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


def get_threads() -> Threads:
    """Sans état propre : tout est dans la communauté, qui garde la base ouverte."""
    return Threads(get_community())


Token = Annotated[str | None, Header(alias="X-Needed-Token")]


def any_user(token: Token = None) -> User:
    return get_community().signed_in(token)


def member_user(token: Token = None) -> User:
    return get_community().signed_in(token, "helper", "patient")


def helper_user(token: Token = None) -> User:
    return get_community().signed_in(token, "helper")


def patient_user(token: Token = None) -> User:
    return get_community().signed_in(token, "patient")


def clinician_user(token: Token = None) -> User:
    return get_community().signed_in(token, "clinician")


def admin_user(token: Token = None) -> User:
    return get_community().signed_in(token, "admin")


Anyone = Annotated[User, Depends(any_user)]
Member = Annotated[User, Depends(member_user)]
Helper = Annotated[User, Depends(helper_user)]
Patient = Annotated[User, Depends(patient_user)]
Clinician = Annotated[User, Depends(clinician_user)]
Admin = Annotated[User, Depends(admin_user)]


@app.post("/api/app/signup", responses=ERROR_RESPONSES)
def signup(body: SignupRequest) -> SessionResponse:
    """Inscription d'un aidant ou d'un patient : e-mail, mot de passe et profil."""
    return get_community().signup(body)


@app.post("/api/app/login", responses=ERROR_RESPONSES)
def login(body: LoginRequest) -> SessionResponse:
    """Connexion de tout compte : aidant, patient, clinicien ou admin."""
    return get_community().login(body.email, body.password)


@app.get("/api/app/demo/accounts")
def demo_accounts() -> list[DemoAccount]:
    """Comptes de démo (`@needed.demo`) pour la connexion rapide de l'accueil."""
    return get_community().demo_accounts()


@app.post("/api/app/logout", responses=ERROR_RESPONSES)
def logout(token: Token = None) -> Ack:
    """Ferme cette session ; les autres sessions du même compte restent ouvertes."""
    get_community().logout(token)
    return Ack()


@app.get("/api/app/me", responses=ERROR_RESPONSES)
def me(user: Anyone) -> AppUser:
    return app_user(user)


@app.patch("/api/app/me", responses=ERROR_RESPONSES)
def update_me(body: ProfileUpdate, user: Anyone) -> AppUser:
    """Change le profil ; de nouveaux centres d'intérêt ou une nouvelle bio refont l'appariement."""
    return get_community().update_profile(user, body)


@app.post("/api/app/feedback", responses=ERROR_RESPONSES)
def feedback(body: FeedbackRequest, token: Token = None) -> Ack:
    """Message à l'équipe, depuis les réglages. Connecté ou non."""
    community = get_community()
    try:
        user = community.signed_in(token) if token else None
    except ApiError:
        user = None  # session expirée : le message part quand même, sans nom
    portals.send_feedback(community.store, user, body)
    return Ack()


# --- Fils de discussion : une demande, sa réponse, le merci et la suite --------------------


@app.get("/api/app/threads", responses=ERROR_RESPONSES)
def threads(user: Member) -> ThreadsResponse:
    return get_threads().for_user(user)


@app.post("/api/app/threads/{thread_id}/messages", responses=ERROR_RESPONSES)
def post_message(thread_id: str, body: MessageRequest, user: Member) -> ThreadsResponse:
    """Écrit dans un fil. Patient face à une demande : sa réponse. Aidant ensuite : son merci."""
    return get_threads().post(user, thread_id, body)


@app.post("/api/app/threads/{thread_id}/decline", responses=ERROR_RESPONSES)
def decline_thread(thread_id: str, user: Patient) -> ThreadsResponse:
    """Le patient laisse passer une demande ; elle sort de son fil, la boucle en apprend."""
    return get_threads().decline(user, thread_id)


# --- Portails : clinicien et admin ----------------------------------------------------------


@app.get("/api/clinician", responses=ERROR_RESPONSES)
def clinician_home(user: Clinician) -> ClinicianHome:
    """Les patients qui ont donné l'e-mail de ce clinicien, sans le contenu de leurs échanges."""
    return portals.clinician_home(get_community().store, user)


@app.put("/api/clinician/patients/{patient_id}/notes", responses=ERROR_RESPONSES)
def clinician_notes(patient_id: str, body: ClinicianNotes, user: Clinician) -> ClinicianHome:
    return portals.save_notes(get_community().store, user, patient_id, body)


@app.get("/api/admin", responses=ERROR_RESPONSES)
def admin_home(user: Admin) -> AdminHome:
    return portals.admin_home(get_community().store, user)


@app.post("/api/admin/feedback/{feedback_id}", responses=ERROR_RESPONSES)
def admin_resolve(feedback_id: str, body: ResolveRequest, user: Admin) -> AdminHome:
    return portals.resolve_feedback(get_community().store, user, feedback_id, body.resolved)


# --- Écrans d'origine de la vraie app (toujours servis) --------------------------------------


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


# --- Montre Garmin : app Connect IQ, liée au patient par un code ---------------------------


@functools.cache
def get_watches() -> Watches:
    return Watches(get_community())


def watch_device(token: Token = None) -> WatchDevice:
    return get_watches().signed_in(token)


Watch = Annotated[WatchDevice, Depends(watch_device)]


@app.post("/api/watch/pair", responses=ERROR_RESPONSES)
def watch_pair() -> WatchPairing:
    """La montre demande un code à afficher, que le patient saisira dans l'app."""
    return get_watches().start_pairing()


@app.get("/api/watch/pair/{pairing_id}", responses=ERROR_RESPONSES)
def watch_pair_status(pairing_id: str) -> WatchPairingStatus:
    """La montre attend que le code soit saisi ; elle reçoit alors son jeton."""
    return get_watches().pairing_status(pairing_id)


@app.post("/api/watch/sync", responses=ERROR_RESPONSES)
def watch_sync(body: WatchReading, device: Watch) -> WatchHome:
    """La montre envoie ses mesures : θ est réestimé, et la demande en attente lui revient."""
    return get_watches().sync(device, body)


@app.post("/api/watch/answer", responses=ERROR_RESPONSES)
def watch_answer(body: WatchAnswer, device: Watch) -> WatchHome:
    """Le patient accepte ou refuse la demande depuis sa montre."""
    return get_watches().answer(device, body.request_id, body.accept)


@app.get("/api/app/patient/watch", responses=ERROR_RESPONSES)
def patient_watch(user: Patient) -> WatchStatus:
    return get_watches().status(user)


@app.post("/api/app/patient/watch", responses=ERROR_RESPONSES)
def patient_watch_link(body: WatchLinkRequest, user: Patient) -> WatchStatus:
    """Le patient saisit le code affiché par sa montre."""
    return get_watches().link(user, body.code)


@app.delete("/api/app/patient/watch", responses=ERROR_RESPONSES)
def patient_watch_unlink(user: Patient) -> WatchStatus:
    return get_watches().unlink(user)


# --- Servir le frontend React buildé (mode tout-en-un et portail web) ---
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
