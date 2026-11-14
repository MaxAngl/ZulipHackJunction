"""Remet la base de la vraie app à zéro et la remplit de comptes fictifs, avec un peu d'histoire.

    uv run python -m backend.seed              # met data/needed.db de côté (.bak), repart de zéro
    uv run python -m backend.seed --offline    # sans Gemini : plus rapide, mesure par mots-clés

Tous les comptes ont le même mot de passe, `needed`. La liste est dans STATUS.md.
Les demandes passent par la vraie boucle (mesure, réponse du patient, apprentissage) : l'état de
chaque patient et ce que voit son clinicien sont donc ceux que l'app aurait calculés.
Arrêter le serveur avant : il garde la base ouverte.
"""

import argparse
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from backend.community import Community
from backend.store import DEFAULT_PATH, Store, User
from ml.model import InterestPair, load_env_file, measure_message

logger = logging.getLogger(__name__)

PASSWORD = "needed"
CLINICIAN_EMAIL = "clinic@needed.demo"


@dataclass(frozen=True)
class Person:
    role: str
    email: str
    first_name: str
    last_name: str
    city: str
    birth_date: str
    interests: tuple[str, ...]
    bio: str


PEOPLE = (
    Person(
        "helper",
        "clara@needed.demo",
        "Clara",
        "Fontaine",
        "Helsinki, Punavuori",
        "1992-07-14",
        ("gardening", "cooking", "reading"),
        "Urban gardener and home cook. Always glad to swap seeds, tips and recipes.",
    ),
    Person(
        "helper",
        "thomas@needed.demo",
        "Thomas",
        "Lindqvist",
        "Espoo, Tapiola",
        "1989-11-23",
        ("photography", "cycling", "hiking"),
        "Film photographer and city cyclist. I love coastal paths and quiet coffee shops.",
    ),
    Person(
        "helper",
        "elena@needed.demo",
        "Elena",
        "Sjöberg",
        "Vantaa, Tikkurila",
        "1995-03-08",
        ("baking", "knitting", "jazz"),
        "Cinnamon bun baker and vinyl collector. Currently learning to knit socks.",
    ),
    Person(
        "patient",
        "julien@needed.demo",
        "Julien",
        "Mercier",
        "Helsinki, Töölö",
        "1994-05-18",
        ("gardening", "baking", "reading"),
        "Growing herbs on my balcony and trying sourdough recipes.",
    ),
    Person(
        "patient",
        "sofia@needed.demo",
        "Sofia",
        "Hakala",
        "Helsinki, Kallio",
        "1996-09-30",
        ("cooking", "jazz", "photography"),
        "Acoustic music, waterfront walks and warm comfort food.",
    ),
    Person(
        "patient",
        "lucas@needed.demo",
        "Lucas",
        "Virtanen",
        "Helsinki, Ullanlinna",
        "1991-01-25",
        ("cycling", "hiking", "knitting"),
        "Fresh air and Scandinavian knitting keep my thoughts light.",
    ),
)

# Couleurs de la charte : cyan sur noir pour les patients, noir sur cyan pour les aidants.
COLORS = {"helper": ("#00D8FF", "#0B0B0B"), "patient": ("#0B0B0B", "#00D8FF")}


def avatar(first_name: str, last_name: str, role: str) -> str:
    """Un avatar sans photo : les initiales, aux couleurs de la charte."""
    background, ink = COLORS.get(role, ("#E5E7EB", "#0B0B0B"))
    initials = f"{first_name[:1]}{last_name[:1]}".upper()
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'>"
        f"<rect width='96' height='96' fill='{background}'/>"
        "<text x='48' y='61' text-anchor='middle' font-family='Arial, sans-serif'"
        f" font-size='36' font-weight='700' fill='{ink}'>{initials}</text></svg>"
    )
    return "data:image/svg+xml;utf8," + quote(svg)


def reset(path: Path) -> None:
    """Met la base actuelle de côté, à côté d'elle ; rien n'est effacé."""
    if path.exists():
        backup = path.with_name(f"{path.stem}.{int(time.time())}.bak")
        path.rename(backup)
        print(f"Ancienne base mise de côté : {backup}")


def deliver(community: Community, helper: User, patient: User, text: str) -> str:
    """Une demande de `helper` à `patient`, mesurée par la vraie chaîne, et transmise."""
    pairs = [
        InterestPair(mine, theirs) for mine in patient.interests for theirs in helper.interests
    ]
    candidate, _review = measure_message(text, pairs)
    request = community.store.add_request(
        helper_id=helper.id,
        patient_id=patient.id,
        text=text,
        patient_interest=candidate.pair.patient_interest,
        helper_interest=candidate.pair.helper_interest,
        lam=candidate.lam,
        format=candidate.format,
        effort=candidate.effort,
        source="real_need",
        status="delivered",
        hold_reason=None,
        delivered_at=time.time(),
    )
    return request.id


def seed(store: Store) -> dict[str, User]:
    community = Community(store)
    people: dict[str, User] = {}
    for person in PEOPLE:
        people[person.first_name] = community.create_account(
            role=person.role,
            email=person.email,
            password=PASSWORD,
            first_name=person.first_name,
            last_name=person.last_name,
            city=person.city,
            birth_date=person.birth_date,
            interests=list(person.interests),
            bio=person.bio,
            avatar_url=avatar(person.first_name, person.last_name, person.role),
            clinician_email=CLINICIAN_EMAIL if person.role == "patient" else None,
        )
        print(f"  {person.role:9} {person.email}")
    clinician = community.create_account(
        role="clinician",
        email=CLINICIAN_EMAIL,
        password=PASSWORD,
        first_name="Aino",
        last_name="Laine",
        city="Helsinki",
        avatar_url=avatar("Aino", "Laine", "clinician"),
    )
    admin = community.create_account(
        role="admin",
        email="admin@needed.demo",
        password=PASSWORD,
        first_name="Team",
        last_name="Needed",
        avatar_url=avatar("Needed", "Team", "admin"),
    )
    print(f"  clinician {clinician.email}\n  admin     {admin.email}")

    clara, thomas, elena = people["Clara"], people["Thomas"], people["Elena"]
    julien, sofia, lucas = people["Julien"], people["Sofia"], people["Lucas"]

    # Clara et Julien : une demande, sa réponse, le merci, puis quelques messages.
    first = deliver(community, clara, julien, "Which herb would you start with on a small balcony?")
    community.reply(
        julien, first, "Basil and chives! Chives come back every year, basil wants full sun."
    )
    community.thank(clara, first, "Chives it is, thank you! My balcony gets morning sun only.")
    store.add_message(first, julien.id, "Then mint will love it too. Keep it in its own pot.")

    # Elena et Lucas : Lucas a répondu, Elena n'a pas encore dit merci.
    second = deliver(
        community, elena, lucas, "What stitch would you suggest for a first pair of mittens?"
    )
    community.reply(lucas, second, "Stockinette with a 2x2 rib cuff. Forgiving and warm.")

    # Thomas et Sofia : la demande attend la réponse de Sofia.
    deliver(community, thomas, sofia, "Any tip to catch warm evening light on the waterfront?")

    store.save_note(
        julien.id,
        clinician.id,
        "Calm, receptive, steady recovery pace",
        "Sourdough baking; volunteering at the community greenhouse",
        "Gardening, jazz records, Scandinavian novels",
    )
    store.add_feedback(
        user_id=julien.id,
        sender_name=julien.full_name,
        sender_role="patient",
        category="suggestion",
        message="Could I get a gentle reminder when a request waits for me?",
    )
    return people


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="sans Gemini")
    parser.add_argument("--db", type=Path, help="base à remplir (par défaut data/needed.db)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    if args.offline:
        os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"] = ""
    else:
        load_env_file()
    path = args.db or Path(os.environ.get("NEEDED_DB") or DEFAULT_PATH)
    reset(path)
    store = Store(path)
    print(f"Comptes créés dans {path} (mot de passe : {PASSWORD}) :")
    seed(store)
    store.close()


if __name__ == "__main__":
    main()
