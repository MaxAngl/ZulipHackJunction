"""Montre Garmin : liaison par code, mesures envoyées par la montre, demande traitée au poignet.

La montre a son propre jeton, distinct de celui du téléphone : délier la montre ne déconnecte pas
le patient. Ses tables vivent dans la même base que le reste de la vraie app.
"""

import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass

from backend import schemas
from backend.community import Community
from backend.errors import ApiError
from backend.store import User

PAIRING_SECONDS = 600
WATCH_REPLY = "Yes, happy to help! (answered from my watch)"

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS watch_pairings (
        id TEXT PRIMARY KEY,
        code TEXT NOT NULL,
        created_at REAL NOT NULL,
        patient_id TEXT,
        token TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS watches (
        token TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        linked_at REAL NOT NULL,
        last_seen REAL,
        last_reading TEXT
    )""",
)


@dataclass(frozen=True)
class WatchDevice:
    token: str
    patient: User


def _first(rows: list[sqlite3.Row]) -> sqlite3.Row | None:
    return rows[0] if rows else None


def measured(reading: schemas.WatchReading) -> dict[str, float]:
    """Les signaux réellement mesurés, sous leurs noms de θ (ml/simulation/spec.py)."""
    values = reading.model_dump(exclude={"local_hour"})
    return {name: float(value) for name, value in values.items() if value is not None}


def _new_code(taken: set[str]) -> str:
    while True:
        code = f"{secrets.randbelow(1_000_000):06d}"
        if code not in taken:
            return code


class Watches:
    def __init__(self, community: Community) -> None:
        self.community = community
        self.store = community.store
        for statement in SCHEMA:
            self.store._run(statement)

    # --- Liaison : la montre affiche un code, le patient le saisit dans l'app ----------------

    def start_pairing(self) -> schemas.WatchPairing:
        now = time.time()
        with self.store.lock:
            recent = self.store._run(
                "SELECT code FROM watch_pairings WHERE created_at > ?", (now - PAIRING_SECONDS,)
            )
            code = _new_code({row["code"] for row in recent})
            pairing_id = uuid.uuid4().hex
            self.store._run(
                "INSERT INTO watch_pairings (id, code, created_at) VALUES (?, ?, ?)",
                (pairing_id, code, now),
            )
        return schemas.WatchPairing(pairing_id=pairing_id, code=code, expires_in=PAIRING_SECONDS)

    def pairing_status(self, pairing_id: str) -> schemas.WatchPairingStatus:
        row = _first(self.store._run("SELECT * FROM watch_pairings WHERE id = ?", (pairing_id,)))
        if row is None:
            raise ApiError(404, "pairing_not_found", "Unknown pairing. Restart the watch app.")
        if time.time() - row["created_at"] > PAIRING_SECONDS:
            return schemas.WatchPairingStatus(status="expired", token=None, patient_name=None)
        if row["token"] is None:
            return schemas.WatchPairingStatus(status="waiting", token=None, patient_name=None)
        patient = self.store.user(row["patient_id"])
        return schemas.WatchPairingStatus(
            status="linked", token=row["token"], patient_name=patient.name if patient else None
        )

    def link(self, patient: User, code: str) -> schemas.WatchStatus:
        now = time.time()
        with self.store.lock:
            row = _first(
                self.store._run(
                    "SELECT id FROM watch_pairings WHERE code = ? AND token IS NULL"
                    " AND created_at > ? ORDER BY created_at DESC",
                    (code, now - PAIRING_SECONDS),
                )
            )
            if row is None:
                raise ApiError(
                    404, "code_not_found", "Unknown or expired code. Reopen Needed on your watch."
                )
            token = uuid.uuid4().hex
            self.store._run("DELETE FROM watches WHERE patient_id = ?", (patient.id,))
            self.store._run(
                "INSERT INTO watches (token, patient_id, linked_at) VALUES (?, ?, ?)",
                (token, patient.id, now),
            )
            self.store._run(
                "UPDATE watch_pairings SET patient_id = ?, token = ? WHERE id = ?",
                (patient.id, token, row["id"]),
            )
        return self.status(patient)

    def status(self, patient: User) -> schemas.WatchStatus:
        fresh = self.store.user(patient.id) or patient
        row = _first(self.store._run("SELECT * FROM watches WHERE patient_id = ?", (patient.id,)))
        if row is None:
            return schemas.WatchStatus(
                linked=False, linked_at=None, last_seen=None, last_reading=None, theta=fresh.theta
            )
        reading = row["last_reading"]
        return schemas.WatchStatus(
            linked=True,
            linked_at=row["linked_at"],
            last_seen=row["last_seen"],
            last_reading=schemas.WatchReading.model_validate_json(reading) if reading else None,
            theta=fresh.theta,
        )

    def unlink(self, patient: User) -> schemas.WatchStatus:
        self.store._run("DELETE FROM watches WHERE patient_id = ?", (patient.id,))
        return self.status(patient)

    # --- Côté montre ----------------------------------------------------------------------

    def signed_in(self, token: str | None) -> WatchDevice:
        row = _first(self.store._run("SELECT * FROM watches WHERE token = ?", (token,)))
        patient = self.store.user(row["patient_id"]) if row else None
        if token is None or patient is None:
            raise ApiError(401, "watch_not_linked", "This watch is not linked. Link it again.")
        return WatchDevice(token, patient)

    def sync(self, device: WatchDevice, reading: schemas.WatchReading) -> schemas.WatchHome:
        """La montre envoie ses mesures : gardées, elles entrent dans θ ; on renvoie la demande."""
        self.store._run(
            "UPDATE watches SET last_seen = ?, last_reading = ? WHERE token = ?",
            (time.time(), reading.model_dump_json(), device.token),
        )
        self.community.push_reading(device.patient, measured(reading))
        return self.home(device.patient)

    def record(self, patient: User, reading: schemas.WatchReading) -> schemas.WatchStatus:
        """Mesures envoyées pour le patient par un autre moyen que l'app montre (`garmin read`)."""
        self.community.push_reading(patient, measured(reading))
        return self.status(patient)

    def answer(self, device: WatchDevice, request_id: str, accept: bool) -> schemas.WatchHome:
        if accept:
            self.community.reply(device.patient, request_id, WATCH_REPLY)
        else:
            self.community.decline(device.patient, request_id)
        return self.home(device.patient)

    def home(self, patient: User) -> schemas.WatchHome:
        fresh = self.store.user(patient.id) or patient
        inbox = self.community.patient_home(fresh).inbox
        request = None
        if inbox:
            request = schemas.WatchRequest(
                id=inbox[0].id, text=inbox[0].text, from_name=inbox[0].with_name
            )
        return schemas.WatchHome(name=fresh.name, theta=fresh.theta, request=request)
