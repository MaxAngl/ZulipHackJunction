"""Chaîne de la boucle côté IA : générer, mesurer, filtrer, choisir trois demandes.

Le modèle de langage propose, il ne décide pas : chaque demande est replacée sur l'axe λ par
une mesure indépendante (embeddings), et seules celles qui tombent dans la zone sont gardées.
"""

import html
import logging
import random
import re
import uuid
from dataclasses import dataclass, replace
from typing import Any

from ml import claude, gemini, lexicon
from ml.embedding import Measure, cosine, embed_texts, measure_kind
from ml.formats import FORMATS, effort_of, guess_format, request_axes
from ml.types import Candidate, InterestPair, Provider, ProviderInfo, Review, Slot, Zone

logger = logging.getLogger(__name__)

CANDIDATES_PER_PAIR = 8
MAX_TEXT_LENGTH = 400

# En dessous de cette ressemblance avec les deux centres d'intérêt, un texte est « hors sujet ».
# Hors ligne, la mesure lexicale donne 0 dès qu'aucun mot-clé n'est présent. Avec de vrais
# embeddings, deux textes se ressemblent toujours un peu. Modèle local : calibré sur des demandes
# sans rapport (« help me move a sofa ») contre des demandes sur le sujet (issue #69). Gemini :
# reste à calibrer.
MIN_RELEVANCE: dict[Measure, float] = {"offline": 0.03, "local": 0.25, "gemini": 0.0}

# Joker (issue #71) : au-delà de cette ressemblance entre l'intérêt du patient et celui de
# l'aidant, c'est le même intérêt. La position entre les deux n'a plus de sens (λ vaut 0,5 pour
# tout texte, ou saute au hasard) : toute demande sur ce sujet commun est dans les intérêts du
# patient, et elle est placée au centre de sa zone. Modèle local, mesuré : gardening × jardinage
# 0,97, photography × photo 0,89, garden 0,88 passent ; knitting × sewing 0,82, baking × cooking
# 0,76 non. Mots-clés : seuls deux noms identiques. Gemini : à calibrer.
SHARED_SIMILARITY: dict[Measure, float] = {"offline": 0.99, "local": 0.85, "gemini": 0.9}
JOKER_WITHOUT_ZONE = 0.5
MIN_POINTS_TO_CALIBRATE = 4

_UNSAFE = re.compile(
    r"\b(money|pay me|loan|bank|password|home address|diagnos|medication|prescri|dose|suicid)"
)

_state = {"note": ""}  # dernier incident Gemini, affiché dans l'interface
_scale = {"gain": 1.0, "shift": 0.0}  # dernier recalage de l'axe pour les embeddings Gemini
_local_scale = {"gain": 1.0, "shift": 0.0}  # idem pour le modèle local (issue #69)

GENERATION_SYSTEM = """You write short requests for a community app where members ask each other \
for small favours.

A member (the asker) is about to ask another member (the recipient) for a small favour. The \
point of every request is to let the recipient feel competent and useful: someone really relies \
on a skill, a taste or an experience of theirs. That only works if the request is real.

What makes a good request (this comes first, before position and format):
- It is a real question the asker needs answered, in a concrete situation of their own: a \
plan, a problem, a choice, a purchase, a first attempt. Say that situation in a few words (what \
for, when, what went wrong).
- The answer is something the asker can act on: a choice between options, a name, an amount, a \
step, a fix, a tip.
- Test each request before writing it: would a sensible adult send this to an acquaintance who \
knows the subject, and would the answer change what they do next? If not, drop it.
- No gimmicks: never a themed mash-up of the two interests (a loaf scored with stars, a scarf in \
team colours, a playlist for houseplants), no whimsical or rhetorical questions ("is that \
silly?", "would you rather"), nothing about fiction, dreams or naming things. Never move the \
recipient's activity into the asker's setting where it does not belong (baking at a campsite, \
knitting in the stands): the asker's setting is the reason for asking, not the place where \
the recipient's hobby happens.
- A memory is asked for because it helps the asker now (a first attempt, a mistake to avoid), \
never out of nostalgia.
- The two members have never met: never refer to a moment they shared.

Blending the two interests of a pair:
- The asker's interest gives the situation, the recipient's interest gives the answer. \
Examples: climbing x cooking: "I'm climbing all day on Saturday. What could I cook on Friday \
that is still good cold at the crag?"; sailing x knitting: "I'm crewing on a boat this autumn. \
Which wool stays warm even when it gets damp?".
- Never glue a sentence about the asker's hobby to an unrelated question about the recipient's \
("I'm planning a bike ride. What's your favourite jazz album?" is wrong). If no real situation \
links the two, write a plain useful question about the recipient's interest instead: a natural \
request a little off the target position is better than a forced one.
- Any reason you give for asking this person must follow from their interest or profile.

Reading the interests:
- Interests are short labels for hobbies: read them as a person would ("dogs" means caring for \
and walking dogs, "reading" means books). Never write a phrase like "get into dogs" or "some \
running".
- Always write in English. Translate labels given in another language ("jardinage" is \
gardening, "cuisine" is cooking).
- If both interests of a pair are the same, the recipient and the asker share it: every request \
is about that shared interest, and requests differ by angle and format, not by position.
- When profiles are given, build on what they actually say. Invent nothing personal about the \
recipient; about the asker, at most a small plausible detail.

Rules:
- Write in the asker's voice, first person, as a short warm message to the recipient.
- Four lines, separated by a line break ("\n"):
  1. a greeting with the recipient's first name ("Hi Emma,");
  2. the request itself: one or two sentences, at most 200 characters, concrete and specific, \
with a capital letter at the start and a question mark or a full stop at the end;
  3. a short friendly closing ("Thanks a lot,");
  4. the asker's first name.
- Vary the greeting and the closing from one request to the next: never use the same greeting \
or the same closing twice in your answer. Greetings such as Hi, Hello, Hey, Good morning, Dear, \
Hi there; closings such as Thanks a lot, Many thanks, Cheers, No rush at all, Thank you in \
advance, Whenever suits you. Invent others too.
- At most one exclamation mark, no emoji.
- Never mention health, mood, wellbeing, therapy, recovery, AI or the app itself.
- Never ask for money, personal data, or medical or legal advice.
- Each request uses exactly one format from the list, and fits its description.
- Every request is a different idea: never send the same question twice with another greeting, \
closing or short add-on.
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
    aim: float | None = None  # banque hors ligne : position que vise son niveau de mélange


_LLM_ERRORS = (gemini.GeminiError, claude.ClaudeError)


def generator() -> Provider:
    """Qui écrit les demandes : Claude si sa clé est là, sinon Gemini, sinon la banque."""
    if claude.is_configured():
        return "claude"
    if gemini.is_configured():
        return "gemini"
    return "offline"


def provider_info() -> ProviderInfo:
    match generator():
        case "claude":
            return ProviderInfo("claude", claude.generation_model(), _state["note"])
        case "gemini":
            return ProviderInfo("gemini", gemini.generation_model(), _state["note"])
    return ProviderInfo("offline", None, "")


def _generate_json(provider: Provider, system: str, prompt: str, schema: dict[str, Any]) -> Any:
    if provider == "claude":
        return claude.generate_json(system, prompt, schema)
    return gemini.generate_json(system, prompt, schema)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def lambda_position(
    a: list[float], p: list[float], h: list[float], provider: Measure = "offline"
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


def _same_name(pair: InterestPair) -> bool:
    return " ".join(pair.patient_interest.lower().split()) == " ".join(
        pair.helper_interest.lower().split()
    )


def _shared(pair: InterestPair, p: list[float], h: list[float], kind: Measure) -> bool:
    """Le patient et l'aidant partagent-ils cet intérêt ? Même nom, ou sens très proche."""
    return _same_name(pair) or cosine(p, h) >= SHARED_SIMILARITY[kind]


def _joker(zone: Zone | None) -> float:
    """Position d'une demande sur un intérêt commun : le centre de la zone du patient."""
    return zone.center if zone is not None else JOKER_WITHOUT_ZONE


def _calibrate(
    raw: list[float], intended: list[float | None], scale: dict[str, float] | None = None
) -> None:
    """Recale l'échelle de l'axe sur un lot généré par Gemini (ou par la banque, mesuré en local).

    Avec de vrais embeddings, une phrase ressemble moins à un mot qu'un mot à un autre : les
    positions brutes se tassent autour de 0,5. On cherche donc la droite qui relie au mieux les
    positions brutes aux positions annoncées par le générateur sur l'ensemble du lot. Chaque
    demande garde sa propre mesure : une demande qui ne tient pas ce qu'elle annonce s'écarte
    de la droite, et c'est sa position mesurée qui compte.
    """
    scale = _scale if scale is None else scale
    points = [(r, t) for r, t in zip(raw, intended, strict=True) if t is not None]
    if len(points) < MIN_POINTS_TO_CALIBRATE:
        return
    mean_raw = sum(r for r, _ in points) / len(points)
    mean_aim = sum(t for _, t in points) / len(points)
    spread = sum((r - mean_raw) ** 2 for r, _ in points)
    together = sum((r - mean_raw) * (t - mean_aim) for r, t in points)
    if spread < 1e-6 or together <= 0:
        return  # mesures toutes égales, ou sans rapport avec les annonces : on ne recale pas
    scale["gain"] = together / spread
    scale["shift"] = mean_aim - scale["gain"] * mean_raw


def _rescaled(raw: float, kind: Measure) -> float:
    if kind == "offline":
        return raw
    scale = _local_scale if kind == "local" else _scale
    return _clip(scale["shift"] + scale["gain"] * raw)


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


def _weight_limit(zone: Zone) -> tuple[str, str, str]:
    """Comment dire au générateur ce qui est trop lourd pour ce patient.

    Renvoie la ligne de consigne, puis la façon de nommer « dans la limite » et « au-delà ».
    Avec une zone à six axes, on nomme les formats permis : un format léger peut être exclu
    (trop d'exposition personnelle, par exemple) alors qu'un plus lourd passe. Avec l'ancienne
    zone, un plafond d'effort suffit.
    """
    if zone.box is None:
        return (
            f"Effort ceiling: {zone.effort_max:.2f}.",
            "at or under the effort ceiling",
            "just above the ceiling",
        )
    suitable = [fmt.key for fmt in FORMATS.values() if zone.box.allows_costs(fmt.axes)]
    if not suitable:  # rien ne passe : on vise le format le plus léger
        suitable = [min(FORMATS.values(), key=lambda fmt: fmt.effort).key]
    return (
        f"Formats that suit this recipient right now: {', '.join(suitable)}.",
        "in one of the formats that suit the recipient",
        "in a format that does not suit them right now",
    )


def _target_line(index: int, pair: InterestPair, center: float) -> str:
    """Ce que la position visée veut dire, en mots, pour une paire."""
    if _same_name(pair):
        return f"{index}. {pair.patient_interest} (shared by both): any request about it"
    return f"{index}. {_mix_words(center, pair.patient_interest, pair.helper_interest)}"


def _profiles_block(patient_name: str, patient_bio: str, helper_name: str, helper_bio: str) -> str:
    lines = [
        f"- {name}: {' '.join(bio.split())}"
        for name, bio in ((patient_name, patient_bio), (helper_name, helper_bio))
        if bio.strip()
    ]
    return "\n\nProfiles, in their own words:\n" + "\n".join(lines) if lines else ""


def _generation_prompt(
    pairs: list[InterestPair],
    zone: Zone,
    helper_name: str,
    patient_name: str,
    avoid: list[str],
    patient_bio: str = "",
    helper_bio: str = "",
) -> str:
    pair_lines = "\n".join(
        f"{index}. {pair.patient_interest} x {pair.helper_interest}"
        for index, pair in enumerate(pairs)
    )
    format_lines = "\n".join(
        f"- {fmt.key} (effort {fmt.effort:.2f}): {fmt.hint}" for fmt in FORMATS.values()
    )
    limit, within, beyond = _weight_limit(zone)
    targets = "\n".join(_target_line(i, pair, zone.center) for i, pair in enumerate(pairs))
    profiles = _profiles_block(patient_name, patient_bio, helper_name, helper_bio)
    avoid_block = ""
    if avoid:
        listed = "\n".join(f"- {text}" for text in avoid[-12:])
        avoid_block = f"\n\nAlready written, do not repeat these ideas:\n{listed}"
    return f"""Asker: {helper_name}. Recipient: {patient_name}.{profiles}

Interest pairs (recipient's interest x asker's interest):
{pair_lines}

Every request sits somewhere between the two interests of its pair. Position is a number:
1.0 = entirely about the recipient's interest, 0.5 = an even bridge, 0.0 = entirely about the \
asker's interest.

Target position: {zone.center:.2f}. In words, for each pair:
{targets}
Acceptable range: {zone.low:.2f} to {zone.high:.2f}.

Formats (use only these keys):
{format_lines}
{limit}

Write {CANDIDATES_PER_PAIR} requests for each pair:
- about two thirds inside the acceptable range and {within}, at different positions within \
the range;
- the others just outside the range or {beyond}, so both limits can be checked;
- vary the formats and never repeat an idea;
- every request passes the test of a real, useful question: when the two interests do not meet \
naturally, stay with the recipient's interest rather than force a mix.{avoid_block}

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


_QUESTION_START = re.compile(
    r"^(could|can|would|will|do|does|did|is|are|was|were|have|has|what|which|how|when|where|who|why)\b",
    re.IGNORECASE,
)


def _tidy(text: str) -> str:
    """Majuscule en tête de chaque ligne ; une demande d'une seule ligne finit par une ponctuation.

    Vu en réel : le modèle léger les oublie parfois, et la demande arrive telle quelle sur le
    téléphone du patient. Les retours à la ligne sont gardés : bonjour, demande, fin, signature.
    Une signature n'a pas de point final : la ponctuation ne touche qu'une ligne seule.
    """
    # Vu en réel : Gemini écrit parfois « In&egrave;s » au lieu de « Inès ».
    lines = [" ".join(line.split()) for line in html.unescape(text).splitlines()]
    lines = [line[0].upper() + line[1:] for line in lines if line]
    if len(lines) == 1 and lines[0][-1] not in ".?!…":
        lines[0] += "?" if _QUESTION_START.match(lines[0]) else "."
    return "\n".join(lines)


# Hors ligne : la demande de la banque, habillée comme le ferait Gemini, sans répéter les formules.
GREETINGS = (
    "Hi {name},",
    "Hello {name},",
    "Hey {name},",
    "Good morning {name},",
    "Dear {name},",
    "Hi there {name},",
    "Hello there {name},",
)
CLOSINGS = (
    "Thanks a lot,",
    "Many thanks,",
    "Cheers,",
    "No rush at all, thank you!",
    "Thank you in advance,",
    "Whenever suits you, thanks!",
    "Thanks so much,",
)


def _dress(body: str, patient_name: str, helper_name: str, greeting: str, closing: str) -> str:
    return "\n".join((greeting.format(name=patient_name), body, closing, helper_name))


def _body(text: str) -> str:
    """La demande seule, sans bonjour ni fin : c'est elle que la banque hors ligne compare."""
    lines = text.splitlines()
    return "\n".join(lines[1:-2]) if len(lines) >= 4 else text


def _draft_with_model(
    provider: Provider,
    pairs: list[InterestPair],
    zone: Zone,
    helper_name: str,
    patient_name: str,
    avoid: list[str],
    bios: tuple[str, str] = ("", ""),
) -> list[_Draft]:
    """Demandes écrites par un modèle de langage (Claude ou Gemini), même prompt pour les deux.

    `bios` : bio du patient, puis de l'aidant.
    """
    prompt = _generation_prompt(pairs, zone, helper_name, patient_name, avoid, *bios)
    data = _generate_json(provider, GENERATION_SYSTEM, prompt, _generation_schema(len(pairs)))
    items = data.get("requests", []) if isinstance(data, dict) else []
    drafts: list[_Draft] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = _tidy(str(item.get("text", "")))
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
        if provider == "claude":
            raise claude.ClaudeError(0, "aucune demande exploitable dans la réponse")
        raise gemini.GeminiError(0, "aucune demande exploitable dans la réponse")
    return drafts


def _draft_offline(
    pairs: list[InterestPair], seed: int, skip: set[str], helper_name: str, patient_name: str
) -> list[_Draft]:
    rng = random.Random(seed)
    greetings, closings = list(GREETINGS), list(CLOSINGS)
    rng.shuffle(greetings)
    rng.shuffle(closings)
    drafts: list[_Draft] = []
    for index, pair in enumerate(pairs):
        requests = lexicon.sample_levels(pair.patient_interest, pair.helper_interest, rng, skip)
        for level, fmt, text in requests:
            n = len(drafts)
            dressed = _dress(
                text,
                patient_name,
                helper_name,
                greetings[n % len(greetings)],
                closings[n % len(closings)],
            )
            aim = 1.0 - level / (lexicon.LEVELS - 1)
            drafts.append(_Draft(index, fmt, dressed, aim=aim))
    return drafts


def _vectors(
    texts: list[str], pairs: list[InterestPair], provider: Provider
) -> tuple[list[list[float]], dict[str, list[float]], Measure]:
    """Vecteurs des textes et des centres d'intérêt, tous par la même mesure.

    `provider` est le générateur : Gemini mesure avec ses embeddings ; sinon le modèle local, et
    la mesure lexicale s'il fait défaut.
    """
    interests = _interest_names(pairs)
    kind = measure_kind(provider)
    try:
        vectors = embed_texts(texts + interests, kind, _dimensions(pairs))
    except RuntimeError as exc:  # modèle local tombé en cours de route
        logger.warning("Mesure locale indisponible, mesure lexicale : %s", exc)
        kind = "offline"
        vectors = embed_texts(texts + interests, kind, _dimensions(pairs))
    by_interest = dict(zip(interests, vectors[len(texts) :], strict=True))
    return vectors[: len(texts)], by_interest, kind


def _measure(
    drafts: list[_Draft], pairs: list[InterestPair], provider: Provider, zone: Zone | None = None
) -> tuple[list[Candidate], set[InterestPair]]:
    """Mesure chaque demande. Renvoie aussi les paires d'intérêt commun (le joker)."""
    vectors, by_interest, kind = _vectors([draft.text for draft in drafts], pairs, provider)
    shared = {
        pair
        for pair in pairs
        if _shared(
            pair, by_interest[pair.patient_interest], by_interest[pair.helper_interest], kind
        )
    }
    measured = [
        lambda_position(
            vector,
            by_interest[pairs[draft.pair_index].patient_interest],
            by_interest[pairs[draft.pair_index].helper_interest],
            kind,
        )
        for draft, vector in zip(drafts, vectors, strict=True)
    ]
    raws = [raw for raw, _ in measured]
    # Une demande sur un intérêt commun n'a pas de vraie position : elle ne recale rien.
    counted = [pairs[draft.pair_index] not in shared for draft in drafts]
    if kind == "gemini":
        aims = [d.intended if keep else None for d, keep in zip(drafts, counted, strict=True)]
        _calibrate(raws, aims)
    elif kind == "local":
        # La banque annonce un niveau de mélange, Claude la position qu'il vise : même recalage
        # que Gemini, chaque demande gardant sa propre mesure.
        aims = [
            (d.aim if d.aim is not None else d.intended) if keep else None
            for d, keep in zip(drafts, counted, strict=True)
        ]
        _calibrate(raws, aims, _local_scale)
    candidates = []
    for draft, (raw, off_topic) in zip(drafts, measured, strict=True):
        if off_topic:
            lam = 0.0
        elif pairs[draft.pair_index] in shared:
            lam = round(_joker(zone), 3)
        else:
            lam = round(_rescaled(raw, kind), 3)
        candidates.append(
            Candidate(
                id=uuid.uuid4().hex[:8],
                text=draft.text,
                pair=pairs[draft.pair_index],
                lam=lam,
                format=draft.format,
                effort=effort_of(draft.format),
                off_topic=off_topic,
                provider=provider,
                intended=draft.intended,
                axes=request_axes(lam, draft.format),
            )
        )
    return candidates, shared


def _estimated(
    drafts: list[_Draft],
    pairs: list[InterestPair],
    zone: Zone | None = None,
    provider: Provider = "gemini",
) -> list[Candidate]:
    """Sans embeddings : la position que le modèle dit avoir visée, à défaut les mots-clés.

    Mode dégradé. La mesure par mots-clés seule place mal les textes d'un modèle (souvent 0 ou 1,
    vu en réel avec Gemini) et la zone n'en garde presque aucun ; le modèle, lui, a écrit pour
    la zone. Un intérêt commun garde le joker.
    """
    lexical, shared = _measure(drafts, pairs, "offline", zone)
    return [
        replace(
            candidate,
            lam=round(draft.intended, 3),
            off_topic=False,
            provider=provider,
            axes=request_axes(draft.intended, candidate.format),
        )
        if draft.intended is not None and candidate.pair not in shared
        else candidate
        for candidate, draft in zip(lexical, drafts, strict=True)
    ]


def generate_candidates(
    pairs: list[InterestPair],
    zone: Zone,
    helper_name: str,
    patient_name: str,
    avoid: list[str],
    seed: int,
    patient_bio: str = "",
    helper_bio: str = "",
) -> list[Candidate]:
    """Étapes 4 et 5 : générer des demandes pour la zone, puis les mesurer.

    Avec Claude ou Gemini si une clé est configurée (Claude d'abord), sinon avec la banque hors
    ligne. En cas d'erreur du modèle, on bascule sur la banque pour cet appel : la démo
    continue. Les demandes de Claude sont mesurées par le modèle d'embeddings local ; si aucune
    mesure par embeddings n'est possible (modèle local absent, ou quota Gemini épuisé, vu en
    réel le 14/11), elles sont placées à la position que le modèle dit avoir visée
    (`_estimated`). Les bios, quand elles sont données, nourrissent le prompt.
    """
    known = set(avoid)
    provider = generator()
    if provider != "offline":
        name = provider.capitalize()
        bios = (patient_bio, helper_bio)
        try:
            drafts = _draft_with_model(
                provider, pairs, zone, helper_name, patient_name, avoid, bios
            )
        except _LLM_ERRORS as exc:
            logger.warning("%s indisponible, bascule hors ligne : %s", name, exc)
            _state["note"] = f"{name} error ({exc.status or 'network'}): built-in bank used."
        else:
            if provider == "claude" and measure_kind("claude") == "offline":
                _state["note"] = "No embedding model: positions estimated by Claude."
                candidates = _estimated(drafts, pairs, zone, "claude")
            else:
                try:
                    candidates, _ = _measure(drafts, pairs, provider, zone)
                    _state["note"] = ""
                except gemini.GeminiError as exc:
                    logger.warning("Embeddings Gemini indisponibles, position estimée : %s", exc)
                    _state["note"] = (
                        f"Gemini embeddings error ({exc.status or 'network'}): "
                        "positions estimated by Gemini."
                    )
                    candidates = _estimated(drafts, pairs, zone)
            return [candidate for candidate in candidates if candidate.text not in known]
    bodies = {_body(text) for text in known}
    drafts = _draft_offline(pairs, seed, bodies, helper_name, patient_name)
    candidates, _ = _measure(drafts, pairs, "offline", zone)
    return [candidate for candidate in candidates if candidate.text not in known]


def review_text(text: str) -> Review:
    """Format, effort et sûreté d'un message écrit ou modifié par l'aidant."""
    provider = generator()
    if provider != "offline":
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
            data = _generate_json(provider, REVIEW_SYSTEM, prompt, schema)
            fmt = data.get("format") if isinstance(data, dict) else None
            if fmt in FORMATS:
                safe = bool(data.get("safe", True))
                return Review(fmt, effort_of(fmt), safe, str(data.get("reason", "")))
        except _LLM_ERRORS as exc:
            logger.warning("Relecture %s indisponible, règle locale utilisée : %s", provider, exc)
    fmt = guess_format(text)
    safe = _UNSAFE.search(text.lower()) is None
    return Review(fmt, effort_of(fmt), safe, "" if safe else "matched a blocked topic")


def _measure_free_text(
    text: str,
    pairs: list[InterestPair],
    preferred: InterestPair | None,
    provider: Provider,
    zone: Zone | None = None,
) -> tuple[InterestPair, float, bool]:
    vectors, by_interest, kind = _vectors([text], pairs, provider)

    def relevance(pair: InterestPair) -> float:
        to_patient = cosine(vectors[0], by_interest[pair.patient_interest])
        to_helper = cosine(vectors[0], by_interest[pair.helper_interest])
        return to_patient + to_helper

    def position(pair: InterestPair) -> tuple[float, bool]:
        raw, off_topic = lambda_position(
            vectors[0],
            by_interest[pair.patient_interest],
            by_interest[pair.helper_interest],
            kind,
        )
        if off_topic:
            return 0.0, True
        p, h = by_interest[pair.patient_interest], by_interest[pair.helper_interest]
        if _shared(pair, p, h, kind):
            return _joker(zone), False
        return _rescaled(raw, kind), False

    if preferred is not None and not position(preferred)[1]:
        return preferred, *position(preferred)
    best = max(pairs, key=relevance)
    return best, *position(best)


def measure_message(
    text: str,
    pairs: list[InterestPair],
    preferred: InterestPair | None = None,
    zone: Zone | None = None,
) -> tuple[Candidate, Review]:
    """Étape 8 : re-mesurer un message modifié ou écrit par l'aidant.

    `pairs` liste les paires possibles (intérêts du patient x intérêts de cet aidant). On garde
    `preferred` si le texte y est encore rattaché, sinon la paire la plus proche du texte.
    Un texte sans lien avec aucun centre d'intérêt reçoit la position 0 (tout côté aidant).
    Sur un intérêt commun, le texte prend le centre de `zone` (le joker), 0,5 sans zone.
    """
    review = review_text(text)
    provider = generator()  # Claude n'a pas d'embeddings : son texte est mesuré en local
    try:
        pair, lam, off_topic = _measure_free_text(text, pairs, preferred, provider, zone)
    except gemini.GeminiError as exc:
        logger.warning("Mesure Gemini indisponible, mesure lexicale utilisée : %s", exc)
        provider = "offline"
        pair, lam, off_topic = _measure_free_text(text, pairs, preferred, provider, zone)
    candidate = Candidate(
        id=uuid.uuid4().hex[:8],
        text=text,
        pair=pair,
        lam=round(lam, 3),
        format=review.format,
        effort=review.effort,
        off_topic=off_topic,
        provider=provider,
        axes=request_axes(lam, review.format),
    )
    return candidate, review


def select_three(
    candidates: list[Candidate], zone: Zone, tried_formats: set[str]
) -> list[tuple[Slot, Candidate]]:
    """Étape 6 : trois demandes de la zone, volontairement différentes.

    - best : la plus proche du cœur de la zone, sur tous ses axes ;
    - bridge : la meilleure d'une autre paire de centres d'intérêt ;
    - explore : un format pas encore essayé avec ce patient, sinon le bord de la zone.
    S'il y a moins de trois demandes dans la zone, on en renvoie moins : on ne triche pas.
    """
    inside = [c for c in candidates if not c.off_topic and zone.contains(c.lam, c.effort, c.axes)]
    inside.sort(key=lambda c: zone.shortfall(c.lam, c.axes))
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
