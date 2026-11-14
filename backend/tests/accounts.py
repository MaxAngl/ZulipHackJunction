"""Comptes de test : un e-mail tiré du prénom, un mot de passe commun."""

from backend.store import Store, User
from ml.model import build_profile

PASSWORD = "secret-pass"


def signup_body(role: str, name: str, interests: list[str], **extra: object) -> dict:
    return {
        "role": role,
        "email": f"{name.lower()}@test.demo",
        "password": PASSWORD,
        "first_name": name,
        "interests": interests,
        **extra,
    }


def account(store: Store, role: str, name: str, interests: list[str]) -> User:
    """Compte écrit directement en base, sans passer par l'API (mot de passe inutilisable)."""
    user = store.add_user(
        email=f"{name.lower()}@test.demo",
        password_hash="-",
        role=role,
        first_name=name,
        interests=interests,
        theta=0.6,
    )
    store.save_profile(user.id, build_profile(interests).to_dict())
    return user
