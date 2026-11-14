"""Mots de passe : PBKDF2-SHA256 de la bibliothèque standard, avec un sel par compte.

Assez pour une démo : aucune dépendance, et un mot de passe n'est jamais stocké en clair.
Le format enregistré dit tout ce qu'il faut pour vérifier : `pbkdf2_sha256$tours$sel$empreinte`.
"""

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ROUNDS = 200_000


def hash_password(password: str, rounds: int = ROUNDS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), rounds).hex()
    return f"{ALGORITHM}${rounds}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds))
    return hmac.compare_digest(candidate.hex(), digest)


def new_token() -> str:
    """Jeton de session : 32 octets tirés par le système, illisibles et impossibles à deviner."""
    return secrets.token_urlsafe(32)
