"""Chaîne de la boucle côté IA : générer, mesurer, filtrer, choisir trois demandes.

Le modèle de langage propose, il ne décide pas : chaque demande est replacée sur l'axe λ par
une mesure indépendante (embeddings), et seules celles qui tombent dans la zone sont gardées.
"""

import logging
import random
import re
import uuid
from dataclasses import dataclass
from typing import Any

from ml import gemini, lexicon
from ml.embedding import cosine, embed_texts
from ml.formats import FORMATS, effort_of, guess_format
from ml.types import Candidate, InterestPair, Provider, ProviderInfo, Review, Slot, Zone

logger = logging.getLogger(__name__)

CANDIDATES_PER_PAIR = 8
MAX_TEXT_LENGTH = 400

# En dessous de cette ressemblance avec les deux centres d'intérêt, un texte est « hors sujet ».
# Hors ligne, la mesure lexicale donne 0 dès qu'aucun mot-clé n'est présent. Avec de vrais
# embeddings, deux textes se ressemblent toujours un peu : le seuil reste à calibrer.
MIN_RELEVANCE: dict[Provider, float] = {"offline": 0.03, "gemini": 0.0}
MIN_POINTS_TO_CALIBRATE = 4

_UNSAFE = re.compile(
    r"\b(money|pay me|loan|bank|password|home address|diagnos|medication|prescri|dose|suicid)"
)

_state = {"note": ""}  # dernier incident Gemini, affiché dans l'interface
_scale = {"gain": 1.0, "shift": 0.0}  # dernier recalage de l'axe pour les embeddings Gemini

GENERATION_SYSTEM = """You write short requests for a community app where members ask each other \
for small favours.

A member (the asker) is about to ask another member (the recipient) for a small favour. It must \
be something the asker would genuinely want, and something the recipient can give thanks to \
what they like or know.

Rules:
- Write in the asker's voice, first person, addressed to the recipient.
- One or two sentences, at most 220 characters. Concrete and specific.
- No greeting, no name, no emoji, no exclamation mark.
- Never mention health, mood, wellbeing, therapy, recovery, AI or the app itself.
- Never ask for money, personal data, or medical or legal advice.
- Each request uses exactly one format from the list, and fits its description.
Return JSON only."""

REVIEW_SYSTEM = """You review one short message that a member of a community app wants to send \
to another member to ask for a small favour. Classify its format and check that it is safe.
Unsafe means: asks for money or personal data, asks for medical or legal advice, is hostile or \
sexual, or pressures the recipient. Return JSON only."""


@dataclass(frozen=True)
class _Draft:
    pair_index: int
    format: str
    text: str
    intended: float | None = None


def provider_info() -> ProviderInfo:
    if gemini.is_configured():
        return ProviderInfo("gemini", gemini.generation_model(), _state["note"])
    return ProviderInfo("offline", None, "")


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def lambda_position(
    a: list[float], p: list[float], h: list[float], provider: Provider = "offline"
) -> tuple[float, bool]:
    """Position d'un texte entre l'intérêt de l'aidant (0) et celui du patient (1).

    C'est la projection du texte sur l'axe qui va de h à p :
        λ = 0,5 + (a·p − a·h) / (2 · (1 − p·h))      (a·x = cosinus entre a et x)
    Un texte identique à p donne 1, identique à h donne 0, à égale distance donne 0,5. Seule la
    différence a·p − a·h compte : ce que le texte partage avec les deux sujets s'annule.
    Le second élément vaut True quand le texte n'a de lien avec aucun des deux sujets : sa
    position est alors 0, tout côté aidant.
    """
    to_patient, to_helper = cosine(a, p), cosine(a, h)
    if max(to_patient, to_helper) < MIN_RELEVANCE[provider]:
        return 0.0, True
    span = max(1e-6, 1.0 - cosine(p, h))
    return _clip(0.5 + (to_patient - to_helper) / (2.0 * span)), False


def _calibrate(raw: list[float], intended: list[float | None]) -> None:
    """Recale l'échelle de l'axe sur un lot généré par Gemini.

    Avec de vrais embeddings, une phrase ressemble moins à un mot qu'un mot à un autre : les
    positions brutes se tassent autour de 0,5. On cherche donc la droite qui relie au mieux les
    positions brutes aux positions annoncées par le générateur sur l'ensemble du lot. Chaque
    demande garde sa propre mesure : une demande qui ne tient pas ce qu'elle annonce s'écarte
    de la droite, et c'est sa position mesurée qui compte.
    """
    points = [(r, t) for r, t in zip(raw, intended, strict=True) if t is not None]
    if len(points) < MIN_POINTS_TO_CALIBRATE:
        return
    mean_raw = sum(r for r, _ in points) / len(points)
    mean_aim = sum(t for _, t in points) / len(points)
    spread = sum((r - mean_raw) ** 2 for r, _ in points)
    together = sum((r - mean_raw) * (t - mean_aim) for r, t in points)
    if spread < 1e-6 or together <= 0:
        return  # mesures toutes égales, ou sans rapport avec les annonces : on ne recale pas
    _scale["gain"] = together / spread
    _scale["shift"] = mean_aim - _scale["gain"] * mean_raw


def _rescaled(raw: float, provider: Provider) -> float:
    if provider == "offline":
        return raw
    return _clip(_scale["shift"] + _scale["gain"] * raw)


def _interest_names(pairs: list[InterestPair]) -> list[str]:
    names = {pair.patient_interest for pair in pairs} | {pair.helper_interest for pair in pairs}
    return sorted(names)


def _dimensions(pairs: list[InterestPair]) -> list[str]:
    names = set(lexicon.all_interests())
    names.update(name.lower() for name in _interest_names(pairs))
    return sorted(names)


def _mix_words(lam: float, patient_interest: str, helper_interest: str) -> str:
    if lam >= 0.85:
        return f"entirely about {patient_interest}"
    if lam >= 0.68:
        return f"mainly about {patient_interest}, with a light touch of {helper_interest}"
    if lam >= 0.55:
        return f"about both, leaning towards {patient_interest}"
    if lam >= 0.45:
        return f"an even bridge between {patient_interest} and {helper_interest}"
    if lam >= 0.3:
        return f"about both, leaning towards {helper_interest}"
    return f"mainly about {helper_interest}, with a light touch of {patient_interest}"


def _generation_prompt(
    pairs: list[InterestPair], zone: Zone, helper_name: str, patient_name: str, avoid: list[str]
) -> str:
    pair_lines = "\n".join(
        f"{index}. {pair.patient_interest} x {pair.helper_interest}"
        for index, pair in enumerate(pairs)
    )
    format_lines = "\n".join(
        f"- {fmt.key} (effort {fmt.effort:.2f}): {fmt.hint}" for fmt in FORMATS.values()
    )
    first = pairs[0]
    target = _mix_words(zone.center, first.patient_interest, first.helper_interest)
    avoid_block = ""
    if avoid:
        listed = "\n".join(f"- {text}" for text in avoid[-12:])
        avoid_block = f"\n\nAlready written, do not repeat these ideas:\n{listed}"
    return f"""Asker: {helper_name}. Recipient: {patient_name}.

Interest pairs (recipient's interest x asker's interest):
{pair_lines}

Every request sits somewhere between the two interests of its pair. Position is a number:
1.0 = entirely about the recipient's interest, 0.5 = an even bridge, 0.0 = entirely about the \
asker's interest.

Target position: {zone.center:.2f} (for pair 0, that means {target}).
Acceptable range: {zone.low:.2f} to {zone.high:.2f}.

Formats (use only these keys):
{format_lines}
Effort ceiling: {zone.effort_max:.2f}.

Write {CANDIDATES_PER_PAIR} requests for each pair:
- about two thirds inside the acceptable range and at or under the effort ceiling, at different \
positions within the range;
- the others just outside the range or just above the ceiling, so both limits can be checked;
- vary the formats and never repeat an idea.{avoid_block}

For each request give "pair" (its number), "format" (a key), "position" (your own estimate, \
0 to 1) and "text"."""


def _generation_schema(pair_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "requests": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pair": {"type": "integer", "minimum": 0, "maximum": pair_count - 1},
                        "format": {"type": "string", "enum": list(FORMATS)},
                        "position": {"type": "number"},
                        "text": {"type": "string"},
                    },
                    "required": ["pair", "format", "text"],
                },
            }
        },
        "required": ["requests"],
    }


def _draft_with_gemini(
    pairs: list[InterestPair], zone: Zone, helper_name: str, patient_name: str, avoid: list[str]
) -> list[_Draft]:
    prompt = _generation_prompt(pairs, zone, helper_name, patient_name, avoid)
    data = gemini.generate_json(GENERATION_SYSTEM, prompt, _generation_schema(len(pairs)))
    items = data.get("requests", []) if isinstance(data, dict) else []
    drafts: list[_Draft] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        pair_index = item.get("pair")
        if not text or len(text) > MAX_TEXT_LENGTH or pair_index not in range(len(pairs)):
            continue
        fmt = item.get("format")
        position = item.get("position")
        intended = float(position) if isinstance(position, int | float) else None
        drafts.append(
            _Draft(
                pair_index=pair_index,
                format=fmt if fmt in FORMATS else guess_format(text),
                text=text,
                intended=min(1.0, max(0.0, intended)) if intended is not None else None,
            )
        )
    if not drafts:
        raise gemini.GeminiError(0, "aucune demande exploitable dans la réponse")
    return drafts


def _draft_offline(pairs: list[InterestPair], seed: int, skip: set[str]) -> list[_Draft]:
    rng = random.Random(seed)
    drafts: list[_Draft] = []
    for index, pair in enumerate(pairs):
        requests = lexicon.sample(pair.patient_interest, pair.helper_interest, rng, skip)
        drafts += [_Draft(index, fmt, text) for fmt, text in requests]
    return drafts


def _measure(
    drafts: list[_Draft], pairs: list[InterestPair], provider: Provider
) -> list[Candidate]:
    dims = _dimensions(pairs)
    interests = _interest_names(pairs)
    vectors = embed_texts([draft.text for draft in drafts] + interests, provider, dims)
    by_interest = dict(zip(interests, vectors[len(drafts) :], strict=True))
    measured = [
        lambda_position(
            vector,
            by_interest[pairs[draft.pair_index].patient_interest],
            by_interest[pairs[draft.pair_index].helper_interest],
            provider,
        )
        for draft, vector in zip(drafts, vectors, strict=False)
    ]
    if provider == "gemini":
        _calibrate([raw for raw, _ in measured], [draft.intended for draft in drafts])
    return [
        Candidate(
            id=uuid.uuid4().hex[:8],
            text=draft.text,
            pair=pairs[draft.pair_index],
            lam=0.0 if off_topic else round(_rescaled(raw, provider), 3),
            format=draft.format,
            effort=effort_of(draft.format),
            off_topic=off_topic,
            provider=provider,
            intended=draft.intended,
        )
        for draft, (raw, off_topic) in zip(drafts, measured, strict=True)
    ]


def generate_candidates(
    pairs: list[InterestPair],
    zone: Zone,
    helper_name: str,
    patient_name: str,
    avoid: list[str],
    seed: int,
) -> list[Candidate]:
    """Étapes 4 et 5 : générer des demandes pour la zone, puis les mesurer.

    Avec Gemini si une clé est configurée, sinon avec la banque hors ligne. En cas d'erreur
    Gemini, on bascule sur la banque pour cet appel : la démo continue.
    """
    known = set(avoid)
    if gemini.is_configured():
        try:
            drafts = _draft_with_gemini(pairs, zone, helper_name, patient_name, avoid)
            candidates = _measure(drafts, pairs, "gemini")
            _state["note"] = ""
            return [candidate for candidate in candidates if candidate.text not in known]
        except gemini.GeminiError as exc:
            logger.warning("Gemini indisponible, bascule hors ligne : %s", exc)
            _state["note"] = f"Gemini error ({exc.status or 'network'}): built-in bank used."
    candidates = _measure(_draft_offline(pairs, seed, known), pairs, "offline")
    return [candidate for candidate in candidates if candidate.text not in known]


def review_text(text: str) -> Review:
    """Format, effort et sûreté d'un message écrit ou modifié par l'aidant."""
    if gemini.is_configured():
        schema = {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": list(FORMATS)},
                "safe": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["format", "safe"],
        }
        formats = "\n".join(f"- {fmt.key}: {fmt.hint}" for fmt in FORMATS.values())
        prompt = f"Formats:\n{formats}\n\nMessage:\n{text}"
        try:
            data = gemini.generate_json(REVIEW_SYSTEM, prompt, schema)
            fmt = data.get("format") if isinstance(data, dict) else None
            if fmt in FORMATS:
                safe = bool(data.get("safe", True))
                return Review(fmt, effort_of(fmt), safe, str(data.get("reason", "")))
        except gemini.GeminiError as exc:
            logger.warning("Relecture Gemini indisponible, règle locale utilisée : %s", exc)
    fmt = guess_format(text)
    safe = _UNSAFE.search(text.lower()) is None
    return Review(fmt, effort_of(fmt), safe, "" if safe else "matched a blocked topic")


def _measure_free_text(
    text: str, pairs: list[InterestPair], preferred: InterestPair | None, provider: Provider
) -> tuple[InterestPair, float, bool]:
    dims = _dimensions(pairs)
    interests = _interest_names(pairs)
    vectors = embed_texts([text, *interests], provider, dims)
    by_interest = dict(zip(interests, vectors[1:], strict=True))

    def relevance(pair: InterestPair) -> float:
        to_patient = cosine(vectors[0], by_interest[pair.patient_interest])
        to_helper = cosine(vectors[0], by_interest[pair.helper_interest])
        return to_patient + to_helper

    def position(pair: InterestPair) -> tuple[float, bool]:
        raw, off_topic = lambda_position(
            vectors[0],
            by_interest[pair.patient_interest],
            by_interest[pair.helper_interest],
            provider,
        )
        return (0.0, True) if off_topic else (_rescaled(raw, provider), False)

    if preferred is not None and not position(preferred)[1]:
        return preferred, *position(preferred)
    best = max(pairs, key=relevance)
    return best, *position(best)


def measure_message(
    text: str, pairs: list[InterestPair], preferred: InterestPair | None = None
) -> tuple[Candidate, Review]:
    """Étape 8 : re-mesurer un message modifié ou écrit par l'aidant.

    `pairs` liste les paires possibles (intérêts du patient x intérêts de cet aidant). On garde
    `preferred` si le texte y est encore rattaché, sinon la paire la plus proche du texte.
    Un texte sans lien avec aucun centre d'intérêt reçoit la position 0 (tout côté aidant).
    """
    review = review_text(text)
    provider: Provider = "gemini" if gemini.is_configured() else "offline"
    try:
        pair, lam, off_topic = _measure_free_text(text, pairs, preferred, provider)
    except gemini.GeminiError as exc:
        logger.warning("Mesure Gemini indisponible, mesure lexicale utilisée : %s", exc)
        provider = "offline"
        pair, lam, off_topic = _measure_free_text(text, pairs, preferred, provider)
    candidate = Candidate(
        id=uuid.uuid4().hex[:8],
        text=text,
        pair=pair,
        lam=round(lam, 3),
        format=review.format,
        effort=review.effort,
        off_topic=off_topic,
        provider=provider,
    )
    return candidate, review


def select_three(
    candidates: list[Candidate], zone: Zone, tried_formats: set[str]
) -> list[tuple[Slot, Candidate]]:
    """Étape 6 : trois demandes de la zone, volontairement différentes.

    - best : la plus proche du centre de la zone ;
    - bridge : la meilleure d'une autre paire de centres d'intérêt ;
    - explore : un format pas encore essayé avec ce patient, sinon le bord de la zone.
    S'il y a moins de trois demandes dans la zone, on en renvoie moins : on ne triche pas.
    """
    inside = [c for c in candidates if not c.off_topic and zone.contains(c.lam, c.effort)]
    inside.sort(key=lambda c: abs(c.lam - zone.center))
    if not inside:
        return []

    chosen: dict[Slot, Candidate] = {"best": inside[0]}

    def remaining() -> list[Candidate]:
        taken = {c.id for c in chosen.values()}
        return [c for c in inside if c.id not in taken]

    bridge = next((c for c in remaining() if c.pair != chosen["best"].pair), None)
    if bridge is not None:
        chosen["bridge"] = bridge

    used_formats = {c.format for c in chosen.values()}
    rest = remaining()
    explore = (
        next((c for c in rest if c.format not in used_formats | tried_formats), None)
        or next((c for c in rest if c.format not in used_formats), None)
        or (rest[-1] if rest else None)
    )
    if explore is not None:
        chosen["explore"] = explore

    slots: tuple[Slot, ...] = ("best", "bridge", "explore")
    for slot in slots:
        rest = remaining()
        if slot not in chosen and rest:
            chosen[slot] = rest[0]
    return [(slot, chosen[slot]) for slot in slots if slot in chosen]
