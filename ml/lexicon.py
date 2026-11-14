"""Mode hors ligne : vocabulaire par centre d'intérêt et banque de demandes.

Sert quand Gemini n'est pas configuré ou ne répond pas. La mesure y est lexicale : un texte est
décrit par les mots-clés de chaque centre d'intérêt qu'il contient, pondérés (les premiers de
chaque liste sont les plus typiques du sujet).
"""

import random
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecipientTopic:
    """Centre d'intérêt du patient : des demandes qui s'appuient sur ce qu'il sait."""

    keywords: tuple[str, ...]
    asks: dict[str, str]  # format -> demande entièrement sur ce sujet
    nod: str  # une phrase qui dit pourquoi on s'adresse à lui


@dataclass(frozen=True)
class AskerTopic:
    """Centre d'intérêt de l'aidant : son contexte, et des demandes ouvertes à tous."""

    keywords: tuple[str, ...]
    context: str  # ce que l'aidant est en train de faire
    lead: str  # une amorce courte, suivie d'une demande
    light: str  # une signature discrète, qui ne contient qu'un mot-clé faible
    faint: tuple[str, ...] = ()  # mots-clés faibles : ils tirent peu la demande vers l'aidant
    outsider: dict[str, str] = field(default_factory=dict)  # format -> demande sur ce sujet


RECIPIENT_TOPICS: dict[str, RecipientTopic] = {
    "gardening": RecipientTopic(
        keywords=("garden", "plant", "herb", "tomato", "balcony", "flower", "seed", "grow"),
        asks={
            "opinion": "Which herb is the easiest to grow on a small balcony?",
            "memory": "What was the first plant you ever kept alive? I'd love to hear the story.",
            "explain": "Could you explain how you prune a tomato plant? A voice note is perfect.",
            "make": "Could you send me a picture of a plant you're proud of and say what it needs?",
            "call": "Could we have a short call so you walk me through starting a herb garden?",
        },
        nod="I trust a gardener's patience on this.",
    ),
    "jazz": RecipientTopic(
        keywords=("jazz", "album", "swing", "saxophone", "record", "playlist", "track"),
        asks={
            "opinion": "Which jazz album would you put on for a quiet Sunday morning?",
            "memory": "What was the best jazz concert you ever went to? Tell me about it.",
            "explain": "Could you explain what makes swing feel like swing? A voice note is great.",
            "make": "Could you put together a five-track jazz playlist for a beginner?",
            "call": "Could we have a short call where you play me one record and say what to hear?",
        },
        nod="I trust a jazz listener's ear on this.",
    ),
    "baking": RecipientTopic(
        keywords=("bak", "bread", "cake", "sourdough", "dough", "oven", "cookie", "loaf"),
        asks={
            "opinion": "What is the one cake you would bake for a birthday?",
            "memory": "What is the first thing you remember baking? I'd love the story.",
            "explain": "Could you explain how you know bread dough has risen enough? A voice note?",
            "make": "Could you bake your favourite cookies this week and show me the result?",
            "call": "Could we have a short call while I try my first sourdough loaf?",
        },
        nod="I trust a baker's precision on this.",
    ),
}

ASKER_TOPICS: dict[str, AskerTopic] = {
    "cooking": AskerTopic(
        keywords=("cook", "dinner", "recipe", "dish", "soup", "pasta", "menu", "meal"),
        context="I'm cooking dinner for six on Saturday.",
        lead="Dinner party coming up:",
        light="Asking from my kitchen.",
        faint=("kitchen",),
        outsider={
            "opinion": "I can't decide between a soup and a pasta dish for Saturday. Your pick?",
            "review": "I wrote a dinner menu. Can I send it so you tell me the weakest dish?",
            "call": "Could we have a short call while I cook? I'd like to think out loud.",
        },
    ),
    "cycling": AskerTopic(
        keywords=("cycl", "bike", "ride", "route", "saddle", "wheel"),
        context="I'm planning a long bike ride for next month.",
        lead="Back from a ride and curious:",
        light="Asking with my helmet still on.",
        faint=("helmet",),
        outsider={
            "opinion": "Two bike routes: along the coast or through the forest. Which one?",
            "review": "I mapped a cycling route. Can I send it so you tell me where to stop?",
            "call": "Could we have a short call so I can talk through my cycling plan?",
        },
    ),
    "photography": AskerTopic(
        keywords=("photo", "camera", "picture", "lens", "portrait"),
        context="I'm practising photography with a new camera this month.",
        lead="Between two photo walks:",
        light="Asking while I set up my tripod.",
        faint=("tripod",),
        outsider={
            "opinion": "I took two photos of the same street. Can I send both so you pick one?",
            "review": "I picked ten pictures for a wall. Can I send them so you say which to drop?",
            "call": "Could we have a short call so I show you my photos and hear what you notice?",
        },
    ),
    "hiking": AskerTopic(
        keywords=("hik", "trail", "summit", "boots", "backpack"),
        context="I'm planning a weekend hike on a new trail.",
        lead="Resting after a hike:",
        light="Asking from the great outdoors.",
        faint=("outdoors",),
        outsider={
            "opinion": "For a day hike, would you start at sunrise or after breakfast?",
            "review": "I listed what I'm packing for a hike. Can I send it so you spot the gaps?",
            "call": "Could we have a short call so you help me choose between two trails?",
        },
    ),
    "woodworking": AskerTopic(
        keywords=("wood", "workshop", "shelf", "bench", "oak", "walnut"),
        context="I'm building a small oak shelf in my workshop.",
        lead="Taking a break in the workshop:",
        light="Asking covered in sawdust.",
        faint=("sawdust",),
        outsider={
            "opinion": "I'm building a shelf: light oak or dark walnut?",
            "review": "I sketched a bench. Can I send the drawing so you say if it looks right?",
            "call": "Could we have a short call while I show you the bench I'm sanding?",
        },
    ),
    "board games": AskerTopic(
        keywords=("board game", "game night", "card game", "dice", "rules", "player"),
        context="I'm hosting a board game night with four players on Friday.",
        lead="Before my game night:",
        light="Asking between two turns at the tabletop.",
        faint=("tabletop",),
        outsider={
            "opinion": "Game night with four players: one long board game or three short ones?",
            "review": "I wrote house rules for a card game. Can I send them so you check them?",
            "call": "Could we have a short call so I explain a game's rules and see if they hold?",
        },
    ),
}

# Combien de demandes prendre par niveau de mélange, du plus proche du patient au plus proche
# de l'aidant. Le tirage couvre ainsi tout l'axe, quelle que soit la zone.
_SAMPLE_PLAN = (2, 3, 3, 3, 2, 1)


FAINT_WEIGHT = 0.35


def weights_for(interest: str) -> dict[str, float]:
    """Poids des mots-clés d'un centre d'intérêt.

    Le premier de la liste pèse 1, les suivants de moins en moins, les mots-clés faibles 0,35.
    Un centre d'intérêt inconnu de la banque n'a qu'un mot-clé : son nom.
    """
    key = interest.lower()
    topic = RECIPIENT_TOPICS.get(key) or ASKER_TOPICS.get(key)
    if topic is None:
        return {key: 1.0}
    weights = {keyword: max(0.5, 1.0 - 0.07 * rank) for rank, keyword in enumerate(topic.keywords)}
    if isinstance(topic, AskerTopic):
        weights.update(dict.fromkeys(topic.faint, FAINT_WEIGHT))
    return weights


def all_interests() -> list[str]:
    return [*RECIPIENT_TOPICS, *ASKER_TOPICS]


def weighted_hits(text: str, interest: str) -> float:
    """Poids total des mots-clés de ce centre d'intérêt présents dans le texte."""
    lowered = text.lower()
    return sum(
        weight * len(re.findall(rf"\b{re.escape(keyword)}", lowered))
        for keyword, weight in weights_for(interest).items()
    )


def _recipient_topic(interest: str) -> RecipientTopic:
    known = RECIPIENT_TOPICS.get(interest.lower())
    if known is not None:
        return known
    return RecipientTopic(
        keywords=(interest.lower(),),
        asks={
            "opinion": f"What would you recommend to someone starting out with {interest}?",
            "memory": f"How did you first get into {interest}? I'd love the story.",
            "explain": f"Could you explain one thing about {interest} that beginners get wrong?",
            "make": f"Could you show me something you did recently with {interest}?",
            "call": f"Could we have a short call so you tell me how to start with {interest}?",
        },
        nod=f"I trust your experience with {interest} on this.",
    )


def _asker_topic(interest: str) -> AskerTopic:
    known = ASKER_TOPICS.get(interest.lower())
    if known is not None:
        return known
    return AskerTopic(
        keywords=(interest.lower(),),
        context=f"I'm spending a lot of time on {interest} lately.",
        lead=f"In the middle of some {interest}:",
        light=f"Asking in the middle of some {interest}.",
        outsider={
            "opinion": f"I have two options for my {interest} project. Can I ask which you'd pick?",
            "review": f"I made something for {interest}. Can I send it and hear what you think?",
            "call": f"Could we have a short call so I talk through my {interest} plans?",
        },
    )


def _after_lead(lead: str, ask: str) -> str:
    return f"{lead} {ask[0].lower()}{ask[1:]}"


def compose(patient_interest: str, helper_interest: str) -> list[list[tuple[str, str]]]:
    """Les demandes possibles pour une paire, par niveau de mélange, sous la forme (format, texte).

    Du niveau 0, entièrement sur l'intérêt du patient, au niveau 5, entièrement sur celui de
    l'aidant. Ce classement n'est qu'une intention : c'est la mesure qui dit où chacune tombe.
    """
    recipient = _recipient_topic(patient_interest)
    asker = _asker_topic(helper_interest)
    asks = list(recipient.asks.items())
    return [
        asks,
        [(fmt, f"{text} {asker.light}") for fmt, text in asks],
        [(fmt, _after_lead(asker.lead, text)) for fmt, text in asks],
        [(fmt, f"{asker.context} {text}") for fmt, text in asks],
        [(fmt, f"{text} {recipient.nod}") for fmt, text in asker.outsider.items()],
        list(asker.outsider.items()),
    ]


def sample(
    patient_interest: str, helper_interest: str, rng: random.Random, skip: set[str]
) -> list[tuple[str, str]]:
    """Un tirage qui couvre tout l'axe, sans reprendre les textes de `skip`."""
    picked: list[tuple[str, str]] = []
    for level, count in zip(compose(patient_interest, helper_interest), _SAMPLE_PLAN, strict=True):
        fresh = [request for request in level if request[1] not in skip]
        rng.shuffle(fresh)
        picked += fresh[:count]
    return picked
