"""Commande de la montre.

    uv run python -m garmin login              # une fois, dans ton terminal (mot de passe, MFA)
    uv run python -m garmin read               # lit Garmin Connect, affiche le relevé et l'état
    uv run python -m garmin read --simulate    # pareil avec une montre simulée (--level 0.3)
    uv run python -m garmin read --push        # envoie aussi l'état au patient de la vraie app

Pour --push : le jeton du patient (NEEDED_PATIENT_TOKEN dans .env, ou --token) se lit dans la
console du navigateur du patient : localStorage.getItem('needed.token.patient').
"""

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime

from garmin.signals import WATCH_SIGNALS, Reading, read_signals
from garmin.simulated import simulated_reading
from ml.model import load_env_file
from ml.simulation.spec import SIGNALS
from ml.watch import Estimate, estimate

DEFAULT_API = "http://localhost:8000"


def push_theta(api_url: str, token: str, theta: float) -> None:
    """Pousse l'état sur la route prévue pour un capteur externe."""
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/app/patient/state",
        data=json.dumps({"theta": round(theta, 4)}).encode(),
        headers={"Content-Type": "application/json", "X-Needed-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def _garmin_reading(now: datetime) -> Reading | None:
    # Import tardif : la montre simulée doit marcher même si garminconnect pose problème.
    from garminconnect import (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )

    from garmin.connect import connect, fetch_raw

    try:
        api = connect()
        return read_signals(fetch_raw(api, now.astimezone().date()), now)
    except GarminConnectAuthenticationError as error:
        print(f"Pas de session Garmin ({error}).")
        print("Lance d'abord, dans ton terminal : uv run python -m garmin login")
    except GarminConnectTooManyRequestsError:
        print("Garmin limite les connexions : attendre quelques minutes.")
    except GarminConnectConnectionError as error:
        print(f"Garmin Connect injoignable : {error}")
    print("En attendant : uv run python -m garmin read --simulate")
    return None


def _show(reading: Reading, result: Estimate, source: str) -> None:
    units = {signal.name: signal.unit for signal in SIGNALS}
    print(f"Relevé de la montre ({source})")
    for name in WATCH_SIGNALS:
        value = reading[name]
        shown = "-" if value is None else f"{value:.1f}"
        print(f"  {name:<24} {shown:>8}  {units[name]}")
    print("Composantes estimées (0 = au plus mal, 1 = au mieux)")
    for name, value in result.components.items():
        print(f"  {name:<24} {value:8.2f}")
    print(f"θ provisoire = {result.theta:.2f}")


def _push(args: argparse.Namespace, theta: float) -> int:
    token = args.token or os.environ.get("NEEDED_PATIENT_TOKEN")
    if not token:
        print("Jeton du patient manquant : --token, ou NEEDED_PATIENT_TOKEN dans .env.")
        print("Console du navigateur du patient : localStorage.getItem('needed.token.patient')")
        return 1
    api_url = args.api or os.environ.get("NEEDED_API_URL") or DEFAULT_API
    try:
        push_theta(api_url, token, theta)
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        try:
            message = json.loads(body)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = body
        print(f"L'app a refusé l'état ({error.code}) : {message}")
        return 1
    except urllib.error.URLError as error:
        print(f"L'app ne répond pas sur {api_url} : {error.reason}")
        return 1
    print(f"θ = {theta:.2f} envoyé au patient sur {api_url}")
    return 0


def _read(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    local = now.astimezone()
    hour = local.hour + local.minute / 60
    if args.simulate:
        reading: Reading | None = simulated_reading(hour, args.level, args.seed)
        source = "simulée"
    else:
        reading = _garmin_reading(now)
        source = "Garmin Connect"
    if reading is None:
        return 1
    try:
        result = estimate(reading, hour)
    except ValueError:
        print("Aucun signal exploitable : la montre s'est-elle synchronisée avec le téléphone ?")
        return 1
    _show(reading, result, source)
    return _push(args, result.theta) if args.push else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m garmin", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login", help="première connexion à Garmin Connect")
    read = commands.add_parser("read", help="lire la montre et calculer l'état")
    read.add_argument("--simulate", action="store_true", help="montre simulée")
    read.add_argument("--level", type=float, help="état du patient simulé, de 0 à 1")
    read.add_argument("--seed", type=int, help="graine du patient simulé")
    read.add_argument("--push", action="store_true", help="envoyer l'état à la vraie app")
    read.add_argument("--token", help="jeton du patient (sinon NEEDED_PATIENT_TOKEN)")
    read.add_argument("--api", help=f"adresse de l'API (sinon NEEDED_API_URL, ou {DEFAULT_API})")
    args = parser.parse_args(argv)
    # Console Windows redirigée (cp1252) : remplacer θ plutôt que planter.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    load_env_file()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    if args.command == "login":
        return _login()
    return _read(args)


def _login() -> int:
    from garminconnect import (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )

    from garmin.connect import login_interactive

    try:
        login_interactive()
    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    ) as error:
        print(f"Connexion refusée : {error}")
        return 1
    print("Connecté. Les jetons sont gardés : plus besoin du mot de passe pour lire la montre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
