"""Stockage de la vraie app : un fichier SQLite, avec la bibliothèque standard.

Quatre tables : les personnes, les demandes, les propositions en attente de chaque aidant, et le
profil d'intérêts de chaque personne (ses vecteurs, calculés une fois à l'inscription).
Le journal des demandes (état avant et après, position, effort, réponse) est ce qui servira
plus tard à entraîner le vrai modèle de zone.
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "needed.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    interests TEXT NOT NULL,
    created_at REAL NOT NULL,
    theta REAL NOT NULL,
    theta_source TEXT NOT NULL,
    zone_offset REAL NOT NULL DEFAULT 0,
    zone_obs INTEGER NOT NULL DEFAULT 0,
    tried_formats TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    helper_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    text TEXT NOT NULL,
    patient_interest TEXT NOT NULL,
    helper_interest TEXT NOT NULL,
    lam REAL NOT NULL,
    format TEXT NOT NULL,
    effort REAL NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    hold_reason TEXT,
    created_at REAL NOT NULL,
    delivered_at REAL,
    answered_at REAL,
    reply TEXT,
    thanks TEXT,
    theta_before REAL,
    theta_after REAL,
    reward REAL
);
CREATE TABLE IF NOT EXISTS suggestions (
    helper_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class User:
    id: str
    token: str
    role: str
    name: str
    interests: list[str]
    created_at: float
    theta: float
    theta_source: str
    zone_offset: float
    zone_obs: int
    tried_formats: list[str]


@dataclass(frozen=True)
class StoredRequest:
    id: str
    helper_id: str
    patient_id: str
    text: str
    patient_interest: str
    helper_interest: str
    lam: float
    format: str
    effort: float
    source: str
    status: str  # held, delivered, answered ou declined
    hold_reason: str | None
    created_at: float
    delivered_at: float | None
    answered_at: float | None
    reply: str | None
    thanks: str | None
    theta_before: float | None
    theta_after: float | None
    reward: float | None


def _user(row: sqlite3.Row) -> User:
    data = dict(row)
    data["interests"] = json.loads(data["interests"])
    data["tried_formats"] = json.loads(data["tried_formats"])
    return User(**data)


class Store:
    def __init__(self, path: str | Path | None = None) -> None:
        target = str(path or os.environ.get("NEEDED_DB") or DEFAULT_PATH)
        if target != ":memory:":
            Path(target).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(target, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        # Une seule connexion partagée entre les fils de FastAPI : on sérialise les accès.
        self.lock = threading.RLock()

    def _run(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.lock:
            rows = self._db.execute(sql, params).fetchall()
            self._db.commit()
            return rows

    # --- Personnes -----------------------------------------------------------------------

    def add_user(self, role: str, name: str, interests: list[str], theta: float) -> User:
        user_id, token = uuid.uuid4().hex[:12], uuid.uuid4().hex
        self._run(
            "INSERT INTO users (id, token, role, name, interests, created_at, theta, theta_source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, token, role, name, json.dumps(interests), time.time(), theta, "onboarding"),
        )
        user = self.user(user_id)
        assert user is not None
        return user

    def user(self, user_id: str) -> User | None:
        rows = self._run("SELECT * FROM users WHERE id = ?", (user_id,))
        return _user(rows[0]) if rows else None

    def user_by_token(self, token: str) -> User | None:
        rows = self._run("SELECT * FROM users WHERE token = ?", (token,))
        return _user(rows[0]) if rows else None

    def patients(self) -> list[User]:
        rows = self._run("SELECT * FROM users WHERE role = 'patient' ORDER BY created_at")
        return [_user(row) for row in rows]

    def helpers(self) -> list[User]:
        rows = self._run("SELECT * FROM users WHERE role = 'helper' ORDER BY created_at")
        return [_user(row) for row in rows]

    def save_profile(self, user_id: str, payload: dict[str, Any]) -> None:
        self._run(
            "INSERT OR REPLACE INTO profiles (user_id, payload) VALUES (?, ?)",
            (user_id, json.dumps(payload)),
        )

    def profile(self, user_id: str) -> dict[str, Any] | None:
        rows = self._run("SELECT payload FROM profiles WHERE user_id = ?", (user_id,))
        return json.loads(rows[0]["payload"]) if rows else None

    def save_patient_model(
        self,
        user_id: str,
        theta: float,
        theta_source: str,
        zone_offset: float,
        zone_obs: int,
        tried_formats: list[str],
    ) -> None:
        self._run(
            "UPDATE users SET theta = ?, theta_source = ?, zone_offset = ?, zone_obs = ?,"
            " tried_formats = ? WHERE id = ?",
            (theta, theta_source, zone_offset, zone_obs, json.dumps(tried_formats), user_id),
        )

    # --- Demandes ------------------------------------------------------------------------

    def add_request(self, **fields: Any) -> StoredRequest:
        request_id = uuid.uuid4().hex[:12]
        record = {"id": request_id, "created_at": time.time(), **fields}
        columns = ", ".join(record)
        marks = ", ".join("?" for _ in record)
        self._run(f"INSERT INTO requests ({columns}) VALUES ({marks})", tuple(record.values()))
        request = self.request(request_id)
        assert request is not None
        return request

    def request(self, request_id: str) -> StoredRequest | None:
        rows = self._run("SELECT * FROM requests WHERE id = ?", (request_id,))
        return StoredRequest(**dict(rows[0])) if rows else None

    def requests_of(self, role: str, user_id: str) -> list[StoredRequest]:
        """Demandes d'un aidant ou d'un patient, de la plus ancienne à la plus récente."""
        column = "helper_id" if role == "helper" else "patient_id"
        rows = self._run(
            f"SELECT * FROM requests WHERE {column} = ? ORDER BY created_at", (user_id,)
        )
        return [StoredRequest(**dict(row)) for row in rows]

    def update_request(self, request_id: str, **fields: Any) -> None:
        assignments = ", ".join(f"{column} = ?" for column in fields)
        self._run(f"UPDATE requests SET {assignments} WHERE id = ?", (*fields.values(), request_id))

    # --- Propositions en attente d'un aidant -----------------------------------------------

    def save_suggestions(self, helper_id: str, patient_id: str, payload: dict[str, Any]) -> None:
        self._run(
            "INSERT OR REPLACE INTO suggestions (helper_id, patient_id, payload, created_at)"
            " VALUES (?, ?, ?, ?)",
            (helper_id, patient_id, json.dumps(payload), time.time()),
        )

    def suggestions(self, helper_id: str) -> tuple[str, dict[str, Any]] | None:
        rows = self._run(
            "SELECT patient_id, payload FROM suggestions WHERE helper_id = ?", (helper_id,)
        )
        return (rows[0]["patient_id"], json.loads(rows[0]["payload"])) if rows else None

    def clear_suggestions(self, helper_id: str) -> None:
        self._run("DELETE FROM suggestions WHERE helper_id = ?", (helper_id,))
