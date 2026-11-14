"""La vraie app : la même boucle que la démo, pour de vraies personnes, avec une base.

Différences avec `backend/loop.py` :
- plusieurs aidants et plusieurs patients, enregistrés dans SQLite (`backend/store.py`) ;
- le patient répond par écrit, l'aidant lit la réponse et remercie ;
- l'état θ n'est plus simulé : il est estimé d'après le comportement du patient dans l'app
  (il répond ou non, vite ou non, longuement ou non), ou poussé par un capteur externe ;
- un patient n'a jamais plus d'une demande à la fois : les autres attendent leur tour.
"""

import time
from dataclasses import asdict

from backend import schemas
from backend.errors import ApiError
from backend.store import Store, StoredRequest, User
from ml.model import (
    Candidate,
    InterestPair,
    InterestProfile,
    Zone,
    ZoneParams,
    build_profile,
    generate_candidates,
    learn,
    measure_message,
    select_three,
    stable_match,
    zone_for,
)

INITIAL_THETA = 0.6  # état à l'inscription, faute de mesure faite à la clinique
PROPOSALS_WANTED = 3

# Estimation de θ d'après le comportement. Chaque événement donne un score entre 0 et 1,
# et θ fait 30 % du chemin vers ce score.
BEHAVIOUR_WEIGHT = 0.3
SCORE_REPLIED = 0.6
BONUS_FAST = 0.2  # réponse en moins d'une heure
BONUS_LONG = 0.2  # réponse d'au moins 80 caractères
SCORE_DECLINED = 0.3
FAST_SECONDS = 3600
LONG_CHARACTERS = 80


def _clamp(value: float) -> float:
    return max(0.02, min(0.98, value))


def suggestion_seed() -> int:
    """Graine du tirage des propositions. Prise sur l'horloge pour varier d'une fois à l'autre.

    Elle ne sert qu'au générateur de secours. Les tests la remplacent par une valeur fixe.
    """
    return int(time.time())


def _clean(interests: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in interests if item.strip()))


class Community:
    def __init__(self, store: Store) -> None:
        self.store = store

    # --- Comptes -------------------------------------------------------------------------

    def join(self, role: schemas.Role, name: str, interests: list[str]) -> schemas.SessionResponse:
        cleaned = _clean(interests)
        if not name.strip() or not cleaned:
            raise ApiError(422, "missing_profile", "Give a first name and at least one interest.")
        user = self.store.add_user(role, name.strip(), cleaned, INITIAL_THETA)
        self._profile(user)  # vecteurs d'intérêts calculés une fois, ici
        return schemas.SessionResponse(token=user.token, user=_user(user))

    def signed_in(self, token: str | None, role: schemas.Role | None = None) -> User:
        user = self.store.user_by_token(token) if token else None
        if user is None:
            raise ApiError(401, "not_signed_in", "Please join first.")
        if role is not None and user.role != role:
            raise ApiError(403, "wrong_role", f"This screen is for {role}s.")
        return user

    # --- Aidant : étapes 2 à 8 ---------------------------------------------------------------

    def helper_home(self, helper: User) -> schemas.HelperHome:
        saved = self.store.suggestions(helper.id)
        patient = self.store.user(saved[0]) if saved else None
        proposals = []
        if saved and patient:
            slots = saved[1]["slots"]
            proposals = [
                schemas.AppProposal(
                    id=item["id"],
                    text=item["text"],
                    patient_interest=item["pair"]["patient_interest"],
                    helper_interest=item["pair"]["helper_interest"],
                )
                for item in sorted(
                    (item for item in saved[1]["candidates"] if item["id"] in slots),
                    key=lambda item: slots.index(item["id"]),
                )
            ]
        return schemas.HelperHome(
            user=_user(helper),
            patient_name=patient.name if patient else None,
            proposals=proposals,
            requests=[
                self._view(request, "helper")
                for request in reversed(self.store.requests_of("helper", helper.id))
            ],
        )

    def suggest(self, helper: User) -> schemas.HelperHome:
        """Choisit un patient, calcule sa zone, génère, mesure et garde trois propositions."""
        with self.store.lock:
            patient = self._pick_patient(helper)
            if patient is None:
                raise ApiError(
                    409, "nobody_yet", "Nobody to ask yet. Invite someone to join first."
                )
            zone = self._zone(patient)
            pairs = self._pairs(helper, patient)
            candidates: list[Candidate] = []
            chosen: list[tuple[str, Candidate]] = []
            for attempt in range(2):  # une seconde génération si la zone est peu fournie
                candidates += generate_candidates(
                    pairs=pairs,
                    zone=zone,
                    helper_name=helper.name,
                    patient_name=patient.name,
                    avoid=[candidate.text for candidate in candidates],
                    seed=suggestion_seed() + attempt,
                )
                chosen = select_three(candidates, zone, set(patient.tried_formats))
                if len(chosen) >= PROPOSALS_WANTED:
                    break
            payload = {
                "candidates": [asdict(candidate) for candidate in candidates],
                "slots": [candidate.id for _, candidate in chosen],
            }
            self.store.save_suggestions(helper.id, patient.id, payload)
            return self.helper_home(helper)

    def send(self, helper: User, proposal_id: str | None, text: str | None) -> schemas.HelperHome:
        with self.store.lock:
            saved = self.store.suggestions(helper.id)
            patient = self.store.user(saved[0]) if saved else None
            if saved is None or patient is None:
                raise ApiError(409, "no_proposals", "Ask for suggestions first.")
            proposal = self._proposal(saved[1], proposal_id) if proposal_id else None
            written = (text or "").strip()
            if proposal is None and not written:
                raise ApiError(422, "empty_message", "Pick a suggestion or write a request.")

            if proposal is not None and written in ("", proposal.text):
                candidate, source = proposal, "suggested"
            else:
                pairs = [
                    InterestPair(mine, theirs)
                    for mine in patient.interests
                    for theirs in helper.interests
                ]
                candidate, review = measure_message(
                    written, pairs, proposal.pair if proposal else None
                )
                if not review.safe:
                    raise ApiError(
                        422, "message_rejected", "This request can't be sent. Please rephrase it."
                    )
                source = "edited" if proposal else "real_need"

            zone = self._zone(patient)
            fits = zone.contains(candidate.lam, candidate.effort) and not candidate.off_topic
            busy = self._pending(patient) is not None
            delivered = fits and not busy
            self.store.add_request(
                helper_id=helper.id,
                patient_id=patient.id,
                text=candidate.text,
                patient_interest=candidate.pair.patient_interest,
                helper_interest=candidate.pair.helper_interest,
                lam=candidate.lam,
                format=candidate.format,
                effort=candidate.effort,
                source=source,
                # Hors zone, ou patient déjà sollicité : retenue, jamais refusée.
                status="delivered" if delivered else "held",
                hold_reason=None if delivered else ("busy" if fits else "outside_zone"),
                delivered_at=time.time() if delivered else None,
            )
            self.store.clear_suggestions(helper.id)
            return self.helper_home(helper)

    def skip(self, helper: User) -> schemas.HelperHome:
        self.store.clear_suggestions(helper.id)
        return self.helper_home(helper)

    def thank(self, helper: User, request_id: str, text: str) -> schemas.HelperHome:
        request = self.store.request(request_id)
        if request is None or request.helper_id != helper.id or request.status != "answered":
            raise ApiError(404, "request_not_found", "This request has no answer to thank for.")
        self.store.update_request(request.id, thanks=text.strip())
        return self.helper_home(helper)

    # --- Patient : étapes 9 à 12 -------------------------------------------------------------

    def patient_home(self, patient: User) -> schemas.PatientHome:
        requests = self.store.requests_of("patient", patient.id)
        return schemas.PatientHome(
            user=_user(patient),
            inbox=[self._view(item, "patient") for item in requests if item.status == "delivered"],
            past=[
                self._view(item, "patient")
                for item in reversed(requests)
                if item.status == "answered"
            ],
        )

    def reply(self, patient: User, request_id: str, text: str) -> schemas.PatientHome:
        with self.store.lock:
            request = self._deliverable(patient, request_id)
            now = time.time()
            waited = now - (request.delivered_at or request.created_at)
            score = SCORE_REPLIED
            score += BONUS_FAST if waited < FAST_SECONDS else 0.0
            score += BONUS_LONG if len(text.strip()) >= LONG_CHARACTERS else 0.0
            self._learn(patient, request, score)
            self.store.update_request(
                request.id, status="answered", reply=text.strip(), answered_at=now
            )
            self._release_held(patient.id)
            return self.patient_home(self._fresh(patient))

    def decline(self, patient: User, request_id: str) -> schemas.PatientHome:
        with self.store.lock:
            request = self._deliverable(patient, request_id)
            self._learn(patient, request, SCORE_DECLINED)
            self.store.update_request(request.id, status="declined", answered_at=time.time())
            self._release_held(patient.id)
            return self.patient_home(self._fresh(patient))

    def push_state(self, patient: User, theta: float) -> schemas.PatientHome:
        """Entrée d'un capteur externe : il fournit θ, la boucle fait le reste."""
        with self.store.lock:
            self.store.save_patient_model(
                patient.id,
                _clamp(theta),
                "sensor",
                patient.zone_offset,
                patient.zone_obs,
                patient.tried_formats,
            )
            self._release_held(patient.id)
            return self.patient_home(self._fresh(patient))

    # --- Intérieur ---------------------------------------------------------------------------

    def _fresh(self, user: User) -> User:
        return self.store.user(user.id) or user

    def _zone(self, patient: User) -> Zone:
        return zone_for(patient.theta, ZoneParams(patient.zone_offset, patient.zone_obs))

    def _pending(self, patient: User) -> StoredRequest | None:
        requests = self.store.requests_of("patient", patient.id)
        return next((item for item in requests if item.status == "delivered"), None)

    def _pick_patient(self, helper: User) -> User | None:
        """Étape 3 : le patient apparié à cet aidant par centres d'intérêt et temps d'attente.

        Mariages stables entre les patients libres et tous les aidants (`ml/matching.py`). Un
        aidant resté sans patient reçoit le patient libre qui attend depuis le plus longtemps.
        """
        patients = [patient for patient in self.store.patients() if patient.id != helper.id]
        if not patients:
            return None
        free = [patient for patient in patients if self._pending(patient) is None] or patients

        now = time.time()
        matched = stable_match(
            {patient.id: self._profile(patient) for patient in free},
            {other.id: self._profile(other) for other in self.store.helpers()},
            {patient.id: now - self._last_asked(patient) for patient in free},
        )
        partner = next((patient for patient in free if matched.get(patient.id) == helper.id), None)
        return partner or min(free, key=self._last_asked)

    def _last_asked(self, patient: User) -> float:
        """Date de la dernière demande ; jamais sollicité : il attend depuis son inscription."""
        requests = self.store.requests_of("patient", patient.id)
        return requests[-1].created_at if requests else patient.created_at

    def _profile(self, user: User) -> InterestProfile:
        """Profil d'intérêts enregistré, ou calculé et enregistré (comptes plus anciens)."""
        saved = self.store.profile(user.id)
        if saved is not None:
            return InterestProfile.from_dict(saved)
        profile = build_profile(user.interests)
        self.store.save_profile(user.id, profile.to_dict())
        return profile

    def _pairs(self, helper: User, patient: User) -> list[InterestPair]:
        turn = len(self.store.requests_of("patient", patient.id))
        mine, theirs = patient.interests, helper.interests
        pairs = [
            InterestPair(mine[turn % len(mine)], theirs[turn % len(theirs)]),
            InterestPair(mine[(turn + 1) % len(mine)], theirs[(turn + 1) % len(theirs)]),
        ]
        return list(dict.fromkeys(pairs))

    def _proposal(self, payload: dict, proposal_id: str) -> Candidate:
        for item in payload["candidates"]:
            if item["id"] == proposal_id and item["id"] in payload["slots"]:
                return Candidate(**{**item, "pair": InterestPair(**item["pair"])})
        raise ApiError(404, "proposal_not_found", "This suggestion is no longer available.")

    def _deliverable(self, patient: User, request_id: str) -> StoredRequest:
        request = self.store.request(request_id)
        if request is None or request.patient_id != patient.id or request.status != "delivered":
            raise ApiError(404, "request_not_found", "This request is no longer waiting.")
        return request

    def _learn(self, patient: User, request: StoredRequest, score: float) -> None:
        """Étapes 10 à 12 : nouvel état d'après le comportement, récompense, mise à jour."""
        theta_before = patient.theta
        theta_after = _clamp(theta_before + BEHAVIOUR_WEIGHT * (score - theta_before))
        reward = theta_after - theta_before  # θ attendu = θ avant : pas de dérive modélisée
        params = learn(
            ZoneParams(patient.zone_offset, patient.zone_obs), theta_before, request.lam, reward
        )
        tried = list(dict.fromkeys([*patient.tried_formats, request.format]))
        self.store.save_patient_model(
            patient.id, theta_after, "behaviour", params.offset, params.n_obs, tried
        )
        self.store.update_request(
            request.id, theta_before=theta_before, theta_after=theta_after, reward=reward
        )

    def _release_held(self, patient_id: str) -> None:
        """Patient libre : transmet la plus ancienne demande retenue qui entre dans la zone."""
        patient = self.store.user(patient_id)
        if patient is None or self._pending(patient) is not None:
            return
        zone = self._zone(patient)
        for request in self.store.requests_of("patient", patient.id):
            if request.status == "held" and zone.contains(request.lam, request.effort):
                self.store.update_request(
                    request.id, status="delivered", hold_reason=None, delivered_at=time.time()
                )
                return

    def _view(self, request: StoredRequest, viewer: schemas.Role) -> schemas.AppRequest:
        other_id = request.patient_id if viewer == "helper" else request.helper_id
        other = self.store.user(other_id)
        if request.status == "answered":
            status = "answered"
        elif viewer == "patient":
            status = "to_answer"
        else:
            # L'aidant ne sait pas si sa demande est retenue, transmise ou mise de côté.
            status = "on_its_way"
        return schemas.AppRequest(
            id=request.id,
            text=request.text,
            with_name=other.name if other else "Someone",
            status=status,
            reply=request.reply,
            thanks=request.thanks,
            created_at=request.created_at,
        )


def _user(user: User) -> schemas.AppUser:
    return schemas.AppUser(id=user.id, role=user.role, name=user.name, interests=user.interests)
