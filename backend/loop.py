"""La boucle IA, pour un patient de démonstration. État en mémoire, remis à zéro au redémarrage.

Les douze étapes :
  Mesurer   1 mesurer θ, lire L(θ)
  Répondre  2 zone · 3 aidant et paires · 4 générer · 5 mesurer et filtrer · 6 proposer trois
            7 l'aidant décide · 8 vérifier le message final · 9 le patient reçoit la demande
  Apprendre 10 mesurer θ à nouveau · 11 récompense · 12 régler le vecteur du patient

Ce qui est appris : l'état L(θ) (autoencodeur), la zone (réseau B) et le vecteur du patient (à
travers le réseau A). Ce qui est simulé : le patient lui-même, c'est-à-dire sa montre et la
façon dont une demande agit sur lui (`ml.model.VirtualPatient`).
"""

import threading
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from backend import schemas
from backend.errors import ApiError
from backend.readout import (
    component_states,
    hold_reason,
    measured_typing,
    signal_states,
    zone_state,
)
from ml.model import (
    FORMATS,
    Candidate,
    InterestPair,
    Outcome,
    Reading,
    Slot,
    VirtualPatient,
    Zone,
    brain,
    format_label,
    generate_candidates,
    measure_message,
    provider_info,
    select_three,
)

INITIAL_THETA = 0.55  # niveau de fond du patient virtuel au départ
PATIENT_SEED = 11  # la même graine redonne le même patient virtuel, donc la même démo
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


class LoopService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.brain = brain()
        self._init_state()

    def _init_state(self) -> None:
        self.body = VirtualPatient(PATIENT_SEED, INITIAL_THETA)
        self.normal = self.brain.normal(self.body.theta)  # ses quatorze jours de référence
        self.vector = np.zeros(8, dtype=np.float32)
        self.outcomes: list[Outcome] = []
        self._read()
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

    def _read(self) -> None:
        """Étapes 1 et 2 : lire L(θ) sur les 28 derniers relevés, puis sortir la zone."""
        self.reading: Reading = self.brain.reading(self.body.theta, self.normal)
        self.zone: Zone = self.brain.zone(self.reading, self.vector)

    # --- Lecture -------------------------------------------------------------------------

    def state(self) -> schemas.LoopState:
        with self._lock:
            return self._snapshot()

    def _zone(self) -> Zone:
        return self.zone

    def _snapshot(self) -> schemas.LoopState:
        zone = self._zone()
        info = provider_info()
        return schemas.LoopState(
            patient=_person(PATIENT),
            helpers=[_person(helper) for helper in HELPERS],
            theta=round(self.reading.wellbeing, 3),
            level=round(self.body.level, 3),
            state=component_states(self.brain, self.reading),
            distance=round(self.brain.distance(self.reading.state), 2),
            signals=signal_states(self.body.theta[-1]),
            formats=[
                schemas.FormatState(key=fmt.key, label=fmt.label, effort=fmt.effort)
                for fmt in FORMATS.values()
            ],
            zone=zone_state(zone),
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
                kind="networks",
                offset=round(zone.center - zone.common_center, 3),
                observations=len(self.outcomes),
                parameters=self.brain.parameters,
                vector=[round(float(value), 3) for value in self.vector],
            ),
        )

    # --- Étape 1 : mesurer ---------------------------------------------------------------

    def set_theta(self, theta: float) -> schemas.LoopState:
        """Le curseur de la démo change l'état caché du patient virtuel. Ses relevés suivent,
        l'autoencodeur relit L(θ), et la zone bouge : on refiltre les demandes déjà mesurées."""
        with self._lock:
            self.body.set_level(theta)
            self._read()
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
                    written, helper_pairs, proposal.pair if proposal else None, zone
                )
                if not review.safe:
                    raise ApiError(
                        422, "message_rejected", "This request can't be sent. Please rephrase it."
                    )
                source = "edited" if proposal else "real_need"

            if _fits(candidate, zone):
                self.message = Message(candidate, self.helper, source, "delivered")
                self.stage = "sent"
            else:
                # Hors zone : retenu, jamais refusé. L'aidant voit le même message d'envoi.
                reason = hold_reason(candidate.lam, candidate.axes, candidate.off_topic, zone)
                held = Message(candidate, self.helper, source, "held", reason)
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
            if _fits(held.candidate, zone):
                self.held.remove(held)
                self.message = replace(held, status="delivered", hold_reason=None)
                self.helper = held.helper
                self.slots = {}
                self.stage = "sent"
                return True
        return False

    # --- Étapes 9 à 12 : réponse du patient, nouvelle mesure, récompense, apprentissage ---

    def respond(
        self, action: schemas.PatientAction, typing: schemas.TypingSignals | None = None
    ) -> schemas.LoopState:
        with self._lock:
            if self.stage != "sent" or self.message is None:
                raise ApiError(409, "no_message", "There is no delivered request to answer.")
            sent = self.message.candidate
            before, zone_before = self.reading, self.zone
            replied = action == "helped"
            axes = sent.axes or (sent.lam, *FORMATS[sent.format].axes)
            # Étape 10 : la demande agit sur le patient virtuel, une journée passe, on relit θ.
            fit, overload = self.body.receive(np.array(axes), replied, measured_typing(typing))
            after = self.brain.reading(self.body.theta, self.normal)
            # Étape 11 : la récompense, de 0 à 100, calculée sur L avant et L après.
            reward = self.brain.reward(before, after)
            # Étape 12 : le vecteur du patient se règle sur toutes ses réactions. B ne change pas.
            self.outcomes.append(Outcome(before.context, tuple(axes), reward, replied))
            self.vector = self.brain.learn(self.outcomes, self.vector)
            center_after = self.brain.zone(before, self.vector).center
            self._read()
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
                    theta_before=round(before.wellbeing, 3),
                    theta_expected=round(before.wellbeing, 3),
                    theta_after=round(after.wellbeing, 3),
                    reward=round(reward, 1),
                    center_before=round(zone_before.center, 3),
                    center_after=round(center_after, 3),
                    fit=round(fit, 2),
                    overload=round(overload, 2),
                )
            )
            self.stage = "answered"
            self.slots = {}
            return self._snapshot()

    def reset(self) -> schemas.LoopState:
        with self._lock:
            self._init_state()
            return self._snapshot()


def _fits(candidate: Candidate, zone: Zone) -> bool:
    if candidate.off_topic:
        return False
    return zone.contains(candidate.lam, candidate.effort, candidate.axes)


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
        in_zone=_fits(candidate, zone),
        off_topic=candidate.off_topic,
        slot=slot,
        provider=candidate.provider,
        axes=list(candidate.axes or ()),
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
        axes=list(candidate.axes or ()),
    )


loop = LoopService()
