"""La vraie app : la même boucle que la démo, pour de vraies personnes, avec une base.

Différences avec `backend/loop.py` :
- plusieurs aidants et plusieurs patients, enregistrés dans SQLite (`backend/store.py`) ;
- le patient répond par écrit, l'aidant lit la réponse et remercie ;
- un patient n'a jamais plus d'une demande à la fois : les autres attendent leur tour.

Comme dans la démo, l'état L(θ), la zone et le vecteur de chaque patient viennent des réseaux
entraînés (`ml.model.brain`). Faute de montre branchée, chaque patient a un corps virtuel
(`ml.model.VirtualPatient`) qui fournit ses relevés θ : c'est la partie SIMULÉE. Ce qui est réel :
les personnes, leurs centres d'intérêt, les demandes, les réponses, et les signaux de frappe que
l'app relève quand le patient écrit.
"""

import hashlib
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from backend import schemas
from backend.errors import ApiError
from backend.readout import measured_typing
from backend.store import Store, StoredRequest, User
from ml.model import (
    Candidate,
    InterestPair,
    InterestProfile,
    Outcome,
    Reading,
    VirtualPatient,
    Zone,
    brain,
    build_profile,
    generate_candidates,
    measure_message,
    request_axes,
    select_three,
    stable_match,
)

INITIAL_THETA = 0.6  # niveau de fond à l'inscription, faute de mesure faite à la clinique
PROPOSALS_WANTED = 3


def suggestion_seed() -> int:
    """Graine du tirage des propositions. Prise sur l'horloge pour varier d'une fois à l'autre.

    Elle ne sert qu'au générateur de secours. Les tests la remplacent par une valeur fixe.
    """
    return int(time.time())


def body_seed(patient_id: str) -> int:
    """Graine du corps virtuel d'un patient : la même personne retrouve le même corps.

    Les tests la remplacent par une valeur fixe.
    """
    return int(hashlib.sha1(patient_id.encode()).hexdigest()[:8], 16)


def _clean(interests: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip().lower() for item in interests if item.strip()))


@dataclass
class _Companion:
    """Ce que la boucle sait d'un patient entre deux requêtes : son corps virtuel, ce que les
    réseaux en lisent, et ce qu'ils ont appris de lui."""

    body: VirtualPatient
    normal: tuple[np.ndarray, np.ndarray]
    reading: Reading
    zone: Zone
    vector: np.ndarray
    outcomes: list[Outcome] = field(default_factory=list)


class Community:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.brain = brain()
        self._companions: dict[str, _Companion] = {}

    # --- Comptes -------------------------------------------------------------------------

    def join(
        self, role: schemas.Role, name: str, interests: list[str], bio: str = ""
    ) -> schemas.SessionResponse:
        cleaned = _clean(interests)
        if not name.strip() or not cleaned:
            raise ApiError(422, "missing_profile", "Give a first name and at least one interest.")
        user = self.store.add_user(role, name.strip(), cleaned, INITIAL_THETA)
        # Vecteurs d'intérêts calculés une fois, ici : les tags et chaque phrase de la bio.
        self.store.save_profile(user.id, build_profile(cleaned, bio).to_dict())
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

            fits = not candidate.off_topic and _fits(
                self._zone(patient), candidate.lam, candidate.format, candidate.effort
            )
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

    def reply(
        self,
        patient: User,
        request_id: str,
        text: str,
        typing: schemas.TypingSignals | None = None,
    ) -> schemas.PatientHome:
        with self.store.lock:
            request = self._deliverable(patient, request_id)
            self._learn(patient, request, replied=True, typing=typing)
            self.store.update_request(
                request.id, status="answered", reply=text.strip(), answered_at=time.time()
            )
            self._release_held(patient.id)
            return self.patient_home(self._fresh(patient))

    def decline(self, patient: User, request_id: str) -> schemas.PatientHome:
        with self.store.lock:
            request = self._deliverable(patient, request_id)
            self._learn(patient, request, replied=False)
            self.store.update_request(request.id, status="declined", answered_at=time.time())
            self._release_held(patient.id)
            return self.patient_home(self._fresh(patient))

    def push_state(self, patient: User, theta: float) -> schemas.PatientHome:
        """Entrée de démonstration : fixe le niveau de fond du corps virtuel du patient.

        Ses relevés suivent, l'autoencodeur relit L(θ), et la zone bouge. Ce réglage n'est pas
        rejoué après un redémarrage du serveur.
        """
        with self.store.lock:
            companion = self._companion(patient)
            companion.body.set_level(theta)
            self._read(companion)
            self._save(patient, companion, "sensor", patient.tried_formats)
            self._release_held(patient.id)
            return self.patient_home(self._fresh(patient))

    # --- Intérieur ---------------------------------------------------------------------------

    def _fresh(self, user: User) -> User:
        return self.store.user(user.id) or user

    def _companion(self, patient: User) -> _Companion:
        """Le corps virtuel du patient et ce que les réseaux en savent.

        Reconstruit à la demande : la même graine redonne le même corps, et l'on rejoue les
        demandes déjà traitées, dans l'ordre. Rien de plus n'a besoin d'être enregistré.
        """
        if patient.id not in self._companions:
            body = VirtualPatient(body_seed(patient.id), INITIAL_THETA)
            normal = self.brain.normal(body.theta)
            reading = self.brain.reading(body.theta, normal)
            vector = np.zeros(8, dtype=np.float32)
            companion = _Companion(body, normal, reading, self.brain.zone(reading, vector), vector)
            past = [
                request
                for request in self.store.requests_of("patient", patient.id)
                if request.status in ("answered", "declined")
            ]
            for request in sorted(past, key=lambda item: item.answered_at or 0.0):
                self._react(companion, request, replied=request.status == "answered")
            self._companions[patient.id] = companion
        return self._companions[patient.id]

    def _read(self, companion: _Companion) -> None:
        companion.reading = self.brain.reading(companion.body.theta, companion.normal)
        companion.zone = self.brain.zone(companion.reading, companion.vector)

    def _react(
        self,
        companion: _Companion,
        request: StoredRequest,
        replied: bool,
        measured: dict[str, float] | None = None,
    ) -> tuple[Reading, float]:
        """Étapes 10 à 12 : la demande agit, une journée passe, on relit θ, on note, on apprend."""
        before = companion.reading
        axes = request_axes(request.lam, request.format)
        companion.body.receive(np.array(axes), replied, measured)
        after = self.brain.reading(companion.body.theta, companion.normal)
        reward = self.brain.reward(before, after)
        companion.outcomes.append(Outcome(before.context, axes, reward, replied))
        companion.vector = self.brain.learn(companion.outcomes, companion.vector)
        self._read(companion)
        return before, reward

    def _zone(self, patient: User) -> Zone:
        return self._companion(patient).zone

    def _save(
        self, patient: User, companion: _Companion, source: str, tried_formats: list[str]
    ) -> None:
        zone = companion.zone
        self.store.save_patient_model(
            patient.id,
            round(companion.reading.wellbeing, 4),
            source,
            round(zone.center - zone.common_center, 4),
            len(companion.outcomes),
            tried_formats,
        )

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
        """Profil d'intérêts enregistré, ou calculé sur les seuls tags (comptes plus anciens)."""
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
                fields = {**item, "pair": InterestPair(**item["pair"])}
                if fields.get("axes") is not None:
                    fields["axes"] = tuple(fields["axes"])
                return Candidate(**fields)
        raise ApiError(404, "proposal_not_found", "This suggestion is no longer available.")

    def _deliverable(self, patient: User, request_id: str) -> StoredRequest:
        request = self.store.request(request_id)
        if request is None or request.patient_id != patient.id or request.status != "delivered":
            raise ApiError(404, "request_not_found", "This request is no longer waiting.")
        return request

    def _learn(
        self,
        patient: User,
        request: StoredRequest,
        replied: bool,
        typing: schemas.TypingSignals | None = None,
    ) -> None:
        """La réaction du patient, vraie, agit sur son corps virtuel ; les réseaux font le reste."""
        companion = self._companion(patient)
        before, reward = self._react(companion, request, replied, measured_typing(typing))
        tried = list(dict.fromkeys([*patient.tried_formats, request.format]))
        self._save(patient, companion, "wearable", tried)
        self.store.update_request(
            request.id,
            theta_before=round(before.wellbeing, 4),
            theta_after=round(companion.reading.wellbeing, 4),
            reward=round(reward, 2),
        )

    def _release_held(self, patient_id: str) -> None:
        """Patient libre : transmet la plus ancienne demande retenue qui entre dans la zone."""
        patient = self.store.user(patient_id)
        if patient is None or self._pending(patient) is not None:
            return
        zone = self._zone(patient)
        for request in self.store.requests_of("patient", patient.id):
            fits = _fits(zone, request.lam, request.format, request.effort)
            if request.status == "held" and fits:
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


def _fits(zone: Zone, lam: float, format_key: str, effort: float) -> bool:
    return zone.contains(lam, effort, request_axes(lam, format_key))


def _user(user: User) -> schemas.AppUser:
    return schemas.AppUser(id=user.id, role=user.role, name=user.name, interests=user.interests)
