"""La boucle IA, pour un patient de démonstration. État en mémoire, remis à zéro au redémarrage.

Les douze étapes :
  Mesurer   1 mesurer θ
  Répondre  2 zone · 3 aidant et paires · 4 générer · 5 mesurer et filtrer · 6 proposer trois
            7 l'aidant décide · 8 vérifier le message final · 9 le patient reçoit la demande
  Apprendre 10 mesurer θ à nouveau · 11 récompense · 12 mettre à jour le modèle
"""

import threading
from dataclasses import dataclass, replace
from typing import Literal

from backend import schemas, sensor
from backend.errors import ApiError
from ml.model import (
    FORMATS,
    Candidate,
    InterestPair,
    Slot,
    Zone,
    ZoneParams,
    format_label,
    generate_candidates,
    learn,
    measure_message,
    provider_info,
    select_three,
    zone_for,
)

INITIAL_THETA = 0.55
PROPOSALS_WANTED = 3
STEP_BY_STAGE: dict[schemas.Stage, int] = {
    "idle": 1,
    "proposed": 7,
    "held": 8,
    "sent": 9,
    "answered": 12,
}


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    interests: tuple[str, ...]


PATIENT = Persona("aino", "Aino", ("gardening", "jazz", "baking"))
HELPERS: tuple[Persona, ...] = (
    Persona("mikko", "Mikko", ("cooking", "cycling")),
    Persona("sara", "Sara", ("photography", "hiking")),
    Persona("leo", "Leo", ("woodworking", "board games")),
)


@dataclass(frozen=True)
class Message:
    candidate: Candidate
    helper: Persona
    source: schemas.MessageSource
    status: Literal["delivered", "held"]
    hold_reason: str | None = None


def _hold_reason(candidate: Candidate, zone: Zone) -> str:
    if candidate.off_topic:
        return "Not linked to the patient's interests."
    if candidate.effort > zone.effort_max:
        return f"Effort {candidate.effort:.2f} is above the ceiling {zone.effort_max:.2f}."
    side = "below" if candidate.lam < zone.low else "above"
    return f"Position {candidate.lam:.2f} is {side} the zone ({zone.low:.2f} to {zone.high:.2f})."


class LoopService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._init_state()

    def _init_state(self) -> None:
        self.theta = INITIAL_THETA
        self.params = ZoneParams()
        self.round_number = 0
        self.stage: schemas.Stage = "idle"
        self.helper: Persona | None = None
        self.pairs: list[InterestPair] = []
        self.candidates: list[Candidate] = []
        self.slots: dict[str, Slot] = {}
        self.message: Message | None = None
        self.held: list[Message] = []
        self.history: list[schemas.HistoryEntry] = []
        self.tried_formats: set[str] = set()

    # --- Lecture -------------------------------------------------------------------------

    def state(self) -> schemas.LoopState:
        with self._lock:
            return self._snapshot()

    def _zone(self) -> Zone:
        return zone_for(self.theta, self.params)

    def _snapshot(self) -> schemas.LoopState:
        zone = self._zone()
        info = provider_info()
        return schemas.LoopState(
            patient=_person(PATIENT),
            helpers=[_person(helper) for helper in HELPERS],
            theta=round(self.theta, 3),
            formats=[
                schemas.FormatState(key=fmt.key, label=fmt.label, effort=fmt.effort)
                for fmt in FORMATS.values()
            ],
            zone=schemas.ZoneState(
                center=round(zone.center, 3),
                low=round(zone.low, 3),
                high=round(zone.high, 3),
                half_width=round(zone.half_width, 3),
                effort_max=round(zone.effort_max, 3),
                common_center=round(zone.common_center, 3),
            ),
            round=schemas.RoundState(
                number=self.round_number,
                stage=self.stage,
                step=STEP_BY_STAGE[self.stage],
                helper_id=self.helper.id if self.helper else None,
                pairs=[_pair(pair) for pair in self.pairs],
                candidates=[
                    _candidate(candidate, zone, self.slots.get(candidate.id))
                    for candidate in self.candidates
                ],
                message=_message(self.message) if self.message else None,
            ),
            held=[_message(message) for message in self.held],
            history=list(self.history),
            generator=schemas.GeneratorState(
                provider=info.provider, model=info.model, note=info.note
            ),
            model=schemas.ModelState(
                offset=round(self.params.offset, 3), observations=self.params.n_obs
            ),
        )

    # --- Étape 1 : mesurer ---------------------------------------------------------------

    def set_theta(self, theta: float) -> schemas.LoopState:
        """Nouvelle mesure de θ. La zone bouge : on refiltre les demandes déjà mesurées."""
        with self._lock:
            self.theta = theta
            if self.stage == "proposed":
                self._pick()
            self._deliver_held()
            return self._snapshot()

    # --- Étapes 2 à 6 : zone, paires, génération, mesure, trois propositions -------------

    def propose(self) -> schemas.LoopState:
        with self._lock:
            if self.stage == "sent":
                raise ApiError(
                    409, "message_pending", "The patient has not answered the last request yet."
                )
            if self._deliver_held():
                return self._snapshot()
            if self.stage != "proposed":
                self._start_round()
            self._generate()
            if len(self.slots) < PROPOSALS_WANTED:
                # Zone peu fournie : une seconde génération, une seule, avant de proposer moins.
                self._generate()
            self.stage = "proposed"
            return self._snapshot()

    def _generate(self) -> None:
        """Étapes 4 à 6 : génère, mesure, puis choisit dans tout ce qui a été mesuré."""
        if self.helper is None:
            return
        self.candidates += generate_candidates(
            pairs=self.pairs,
            zone=self._zone(),
            helper_name=self.helper.name,
            patient_name=PATIENT.name,
            avoid=[candidate.text for candidate in self.candidates],
            seed=self.round_number * 100 + len(self.candidates),
        )
        self._pick()

    def _start_round(self) -> None:
        """Étape 3. SIMULÉ : l'aidant et les paires tournent à chaque manche."""
        self.round_number += 1
        turn = self.round_number - 1
        self.helper = HELPERS[turn % len(HELPERS)]
        patient, helper = PATIENT.interests, self.helper.interests
        self.pairs = [
            InterestPair(patient[turn % len(patient)], helper[turn % len(helper)]),
            InterestPair(patient[(turn + 1) % len(patient)], helper[(turn + 1) % len(helper)]),
        ]
        self.candidates = []
        self.slots = {}
        self.message = None

    def _pick(self) -> None:
        chosen = select_three(self.candidates, self._zone(), self.tried_formats)
        self.slots = {candidate.id: slot for slot, candidate in chosen}

    # --- Étapes 7 et 8 : l'aidant décide, le message final est vérifié --------------------

    def send(self, proposal_id: str | None, text: str | None) -> schemas.LoopState:
        with self._lock:
            if self.stage != "proposed" or self.helper is None:
                raise ApiError(409, "no_proposals", "Run the loop first: nothing to send yet.")
            proposal = self._proposal(proposal_id) if proposal_id else None
            written = (text or "").strip()
            if proposal is None and not written:
                raise ApiError(422, "empty_message", "Pick a suggestion or write a request.")

            zone = self._zone()
            if proposal is not None and written in ("", proposal.text):
                candidate, source = proposal, "suggested"
            else:
                helper_pairs = [
                    InterestPair(mine, theirs)
                    for mine in PATIENT.interests
                    for theirs in self.helper.interests
                ]
                candidate, review = measure_message(
                    written, helper_pairs, proposal.pair if proposal else None
                )
                if not review.safe:
                    raise ApiError(
                        422, "message_rejected", "This request can't be sent. Please rephrase it."
                    )
                source = "edited" if proposal else "real_need"

            if zone.contains(candidate.lam, candidate.effort) and not candidate.off_topic:
                self.message = Message(candidate, self.helper, source, "delivered")
                self.stage = "sent"
            else:
                # Hors zone : retenu, jamais refusé. L'aidant voit le même message d'envoi.
                held = Message(
                    candidate, self.helper, source, "held", _hold_reason(candidate, zone)
                )
                self.held.append(held)
                self.message = held
                self.stage = "held"
            return self._snapshot()

    def skip(self) -> schemas.LoopState:
        """L'aidant passe son tour : rien n'est envoyé."""
        with self._lock:
            if self.stage != "proposed":
                raise ApiError(409, "no_proposals", "There is no suggestion to skip.")
            self.stage = "idle"
            self.candidates = []
            self.slots = {}
            return self._snapshot()

    def _proposal(self, proposal_id: str) -> Candidate:
        for candidate in self.candidates:
            if candidate.id == proposal_id and candidate.id in self.slots:
                return candidate
        raise ApiError(404, "proposal_not_found", "This suggestion is no longer available.")

    def _deliver_held(self) -> bool:
        """Transmet un message retenu dès qu'il entre dans la zone. Un seul à la fois."""
        if self.stage == "sent":
            return False
        zone = self._zone()
        for held in self.held:
            if zone.contains(held.candidate.lam, held.candidate.effort):
                self.held.remove(held)
                self.message = replace(held, status="delivered", hold_reason=None)
                self.helper = held.helper
                self.slots = {}
                self.stage = "sent"
                return True
        return False

    # --- Étapes 9 à 12 : réponse du patient, nouvelle mesure, récompense, apprentissage ---

    def respond(self, action: schemas.PatientAction) -> schemas.LoopState:
        with self._lock:
            if self.stage != "sent" or self.message is None:
                raise ApiError(409, "no_message", "There is no delivered request to answer.")
            sent = self.message.candidate
            theta_before = self.theta
            theta_expected = sensor.expected_theta(theta_before)
            theta_after = sensor.theta_after(
                theta_before, sent.lam, sent.effort, helped=action == "helped"
            )
            reward = theta_after - theta_expected
            center_before = zone_for(theta_before, self.params).center
            self.params = learn(self.params, theta_before, sent.lam, reward)
            center_after = zone_for(theta_before, self.params).center
            self.theta = theta_after
            self.tried_formats.add(sent.format)
            self.history.append(
                schemas.HistoryEntry(
                    number=self.round_number,
                    helper_name=self.message.helper.name,
                    text=sent.text,
                    lam=sent.lam,
                    effort=sent.effort,
                    format_label=format_label(sent.format),
                    source=self.message.source,
                    action=action,
                    theta_before=round(theta_before, 3),
                    theta_expected=round(theta_expected, 3),
                    theta_after=round(theta_after, 3),
                    reward=round(reward, 3),
                    center_before=round(center_before, 3),
                    center_after=round(center_after, 3),
                )
            )
            self.stage = "answered"
            self.slots = {}
            return self._snapshot()

    def reset(self) -> schemas.LoopState:
        with self._lock:
            self._init_state()
            return self._snapshot()


def _person(persona: Persona) -> schemas.Person:
    return schemas.Person(id=persona.id, name=persona.name, interests=list(persona.interests))


def _pair(pair: InterestPair) -> schemas.InterestPair:
    return schemas.InterestPair(
        patient_interest=pair.patient_interest, helper_interest=pair.helper_interest
    )


def _candidate(candidate: Candidate, zone: Zone, slot: Slot | None) -> schemas.CandidateState:
    return schemas.CandidateState(
        id=candidate.id,
        text=candidate.text,
        pair=_pair(candidate.pair),
        lam=candidate.lam,
        intended=candidate.intended,
        format=candidate.format,
        format_label=format_label(candidate.format),
        effort=candidate.effort,
        in_zone=not candidate.off_topic and zone.contains(candidate.lam, candidate.effort),
        off_topic=candidate.off_topic,
        slot=slot,
        provider=candidate.provider,
    )


def _message(message: Message) -> schemas.MessageState:
    candidate = message.candidate
    return schemas.MessageState(
        id=candidate.id,
        text=candidate.text,
        helper_id=message.helper.id,
        pair=_pair(candidate.pair),
        lam=candidate.lam,
        format=candidate.format,
        format_label=format_label(candidate.format),
        effort=candidate.effort,
        source=message.source,
        status=message.status,
        hold_reason=message.hold_reason,
    )


loop = LoopService()
