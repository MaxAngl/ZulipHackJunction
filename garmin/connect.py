"""Garmin Connect avec `garminconnect` (bibliothèque non officielle).

La première connexion demande l'email, le mot de passe et le code MFA dans le terminal, puis
garde les jetons dans GARMINTOKENS (par défaut ~/.garminconnect, hors du repo). Le mot de passe
n'est jamais écrit sur le disque. Les fois suivantes, seuls les jetons servent.
"""

import getpass
import logging
import os
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin, GarminConnectConnectionError

logger = logging.getLogger(__name__)


def tokenstore() -> str:
    return os.environ.get("GARMINTOKENS") or "~/.garminconnect"


def login_interactive() -> None:
    """Première connexion, à lancer soi-même dans un terminal."""
    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password: ")
    api = Garmin(email, password, prompt_mfa=lambda: input("MFA code: ").strip())
    api.login(tokenstore())


def connect() -> Garmin:
    """Session à partir des jetons gardés. Lève GarminConnectAuthenticationError sans eux."""
    api = Garmin()
    api.login(tokenstore())
    return api


def _call(key: str, call: Callable[[], Any]) -> Any:
    try:
        return call()
    except GarminConnectConnectionError as error:
        logger.warning("Garmin : %s indisponible (%s)", key, error)
        return None


def _has_night(sleep: Any) -> bool:
    return bool(((sleep or {}).get("dailySleepDTO") or {}).get("sleepTimeSeconds"))


def fetch_raw(api: Garmin, day: date) -> dict[str, Any]:
    """Réponses brutes du jour. Une réponse manquante vaut None ; les autres sont gardées.

    Sans nuit enregistrée ce jour-là (montre retirée, nuit blanche), on prend la nuit de la
    veille : les signaux de la nuit gardent leur dernière valeur connue (docs/modele.md, 11).
    """
    cdate = day.isoformat()
    calls = {
        "summary": lambda: api.get_user_summary(cdate),
        "heart_rates": lambda: api.get_heart_rates(cdate),
        "stress": lambda: api.get_stress_data(cdate),
        "respiration": lambda: api.get_respiration_data(cdate),
        "steps": lambda: api.get_steps_data(cdate),
        "sleep": lambda: api.get_sleep_data(cdate),
        "hrv": lambda: api.get_hrv_data(cdate),
        "activities": lambda: api.get_activities_by_date(cdate, cdate),
    }
    raw = {key: _call(key, call) for key, call in calls.items()}
    if not _has_night(raw["sleep"]):
        previous = (day - timedelta(days=1)).isoformat()
        sleep = _call("sleep", lambda: api.get_sleep_data(previous))
        if _has_night(sleep):
            logger.warning(
                "Garmin : pas de nuit enregistrée le %s, nuit du %s utilisée", cdate, previous
            )
            raw["sleep"] = sleep
            raw["hrv"] = _call("hrv", lambda: api.get_hrv_data(previous))
    return raw
