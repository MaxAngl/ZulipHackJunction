"""Stockage de la vraie app : un fichier SQLite, avec la bibliothèque standard.

Tables : les comptes et leurs sessions, les demandes, les propositions en attente de chaque
aidant, le profil d'intérêts de chaque personne, les messages des fils, les besoins publiés par
les patients, les notes des cliniciens et les messages envoyés à l'équipe.
Le journal des demandes (état avant et après, position, effort, réponse) est ce qui servira
plus tard à entraîner le vrai modèle de zone.

Le schéma est versionné (`PRAGMA user_version`). Une base d'une version plus ancienne est mise de
côté au démarrage (renommée en `.bak`), et une base neuve la remplace : rien n'est migré.
"""

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "needed.db"
SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    birth_date TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    avatar_url TEXT,
    passion_photos TEXT NOT NULL DEFAULT '[]',
    clinician_email TEXT,
    allow_profile_view INTEGER NOT NULL DEFAULT 1,
    interests TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL,
    theta REAL NOT NULL,
    theta_source TEXT NOT NULL DEFAULT 'onboarding',
    zone_offset REAL NOT NULL DEFAULT 0,
    zone_obs INTEGER NOT NULL DEFAULT 0,
    tried_formats TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at REAL NOT NULL
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
    thanked_at REAL,
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
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    text TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS needs (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    helper_id TEXT,
    created_at REAL NOT NULL,
    taken_at REAL
);
CREATE TABLE IF NOT EXISTS clinician_notes (
    patient_id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL,
    mood TEXT NOT NULL,
    proud TEXT NOT NULL,
    loves TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    sender_name TEXT NOT NULL,
    sender_role TEXT NOT NULL,
    category TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at REAL NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS messages_by_thread ON messages (thread_id, created_at);
CREATE INDEX IF NOT EXISTS requests_by_patient ON requests (patient_id, created_at);
CREATE INDEX IF NOT EXISTS requests_by_helper ON requests (helper_id, created_at);
"""

_JSON_COLUMNS = ("interests", "tried_formats", "passion_photos")


@dataclass(frozen=True)
class User:
    id: str
    email: str
    password_hash: str
    role: str  # helper, patient, clinician ou admin
    first_name: str
    last_name: str
    city: str
    birth_date: str
    bio: str
    avatar_url: str | None
    passion_photos: list[str]
    clinician_email: str | None
    allow_profile_view: bool
    interests: list[str]
    created_at: float
    theta: float
    theta_source: str
    zone_offset: float
    zone_obs: int
    tried_formats: list[str]

    @property
    def name(self) -> str:
        """Le prénom : c'est ainsi que l'app et les demandes s'adressent à quelqu'un."""
        return self.first_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


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
    thanked_at: float | None
    theta_before: float | None
    theta_after: float | None
    reward: float | None


@dataclass(frozen=True)
class StoredMessage:
    id: str
    thread_id: str
    sender_id: str
    text: str
    attachments: list[dict[str, Any]]
    created_at: float


@dataclass(frozen=True)
class StoredNeed:
    id: str
    patient_id: str
    text: str
    status: str  # open, taken ou closed
    helper_id: str | None
    created_at: float
    taken_at: float | None


@dataclass(frozen=True)
class StoredNote:
    patient_id: str
    author_id: str
    mood: str
    proud: str
    loves: str
    updated_at: float


@dataclass(frozen=True)
class StoredFeedback:
    id: str
    user_id: str | None
    sender_name: str
    sender_role: str
    category: str
    message: str
    created_at: float
    resolved: bool


def _user(row: sqlite3.Row) -> User:
    data = dict(row)
    for column in _JSON_COLUMNS:
        data[column] = json.loads(data[column])
    data["allow_profile_view"] = bool(data["allow_profile_view"])
    return User(**data)


def _encode(fields: dict[str, Any]) -> dict[str, Any]:
    encoded = dict(fields)
    for column in _JSON_COLUMNS:
        if column in encoded:
            encoded[column] = json.dumps(encoded[column])
    if "allow_profile_view" in encoded:
        encoded["allow_profile_view"] = int(bool(encoded["allow_profile_view"]))
    return encoded


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _set_aside_old_database(target: str) -> None:
    """Base d'un schéma plus ancien : renommée à côté, pour qu'une base neuve la remplace."""
    path = Path(target)
    if not path.exists():
        return
    with sqlite3.connect(target) as probe:
        version = probe.execute("PRAGMA user_version").fetchone()[0]
        tables = probe.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()
    probe.close()
    if version >= SCHEMA_VERSION or tables[0] == 0:
        return
    backup = path.with_name(f"{path.stem}.v{version}-{int(time.time())}.bak")
    path.rename(backup)
    logger.warning("Ancienne base mise de côté : %s (schéma %s)", backup, version)


class Store:
    def __init__(self, path: str | Path | None = None) -> None:
        target = str(path or os.environ.get("NEEDED_DB") or DEFAULT_PATH)
        if target != ":memory:":
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            _set_aside_old_database(target)
        self.path = target
        self._db = sqlite3.connect(target, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._db.commit()
        # Une seule connexion partagée entre les fils de FastAPI : on sérialise les accès.
        self.lock = threading.RLock()

    def close(self) -> None:
        with self.lock:
            self._db.close()

    def _run(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.lock:
            rows = self._db.execute(sql, params).fetchall()
            self._db.commit()
            return rows

    def _insert(self, table: str, record: dict[str, Any]) -> None:
        columns = ", ".join(record)
        marks = ", ".join("?" for _ in record)
        self._run(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(record.values()))

    def _update(self, table: str, key: str, key_value: str, fields: dict[str, Any]) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{column} = ?" for column in fields)
        self._run(
            f"UPDATE {table} SET {assignments} WHERE {key} = ?", (*fields.values(), key_value)
        )

    # --- Comptes -------------------------------------------------------------------------

    def add_user(self, **fields: Any) -> User:
        """Crée un compte. `email`, `password_hash`, `role`, `first_name` et `theta` sont requis."""
        user_id = _new_id()
        self._insert("users", {"id": user_id, "created_at": time.time(), **_encode(fields)})
        user = self.user(user_id)
        assert user is not None
        return user

    def update_user(self, user_id: str, **fields: Any) -> None:
        self._update("users", "id", user_id, _encode(fields))

    def user(self, user_id: str) -> User | None:
        rows = self._run("SELECT * FROM users WHERE id = ?", (user_id,))
        return _user(rows[0]) if rows else None

    def user_by_email(self, email: str) -> User | None:
        rows = self._run("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
        return _user(rows[0]) if rows else None

    def users(self, role: str | None = None) -> list[User]:
        if role is None:
            rows = self._run("SELECT * FROM users ORDER BY created_at")
        else:
            rows = self._run("SELECT * FROM users WHERE role = ? ORDER BY created_at", (role,))
        return [_user(row) for row in rows]

    def patients(self) -> list[User]:
        return self.users("patient")

    def helpers(self) -> list[User]:
        return self.users("helper")

    def patients_of_clinician(self, email: str) -> list[User]:
        rows = self._run(
            "SELECT * FROM users WHERE role = 'patient' AND clinician_email = ?"
            " ORDER BY created_at",
            (email.strip().lower(),),
        )
        return [_user(row) for row in rows]

    # --- Sessions ------------------------------------------------------------------------

    def add_session(self, user_id: str, token: str) -> None:
        self._insert("sessions", {"token": token, "user_id": user_id, "created_at": time.time()})

    def user_by_session(self, token: str) -> User | None:
        rows = self._run(
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id"
            " WHERE sessions.token = ?",
            (token,),
        )
        return _user(rows[0]) if rows else None

    def delete_session(self, token: str) -> None:
        self._run("DELETE FROM sessions WHERE token = ?", (token,))

    # --- Profil d'intérêts ------------------------------------------------------------------

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
        self.update_user(
            user_id,
            theta=theta,
            theta_source=theta_source,
            zone_offset=zone_offset,
            zone_obs=zone_obs,
            tried_formats=tried_formats,
        )

    # --- Demandes ------------------------------------------------------------------------

    def add_request(self, **fields: Any) -> StoredRequest:
        request_id = _new_id()
        self._insert("requests", {"id": request_id, "created_at": time.time(), **fields})
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

    def all_requests(self) -> list[StoredRequest]:
        rows = self._run("SELECT * FROM requests ORDER BY created_at")
        return [StoredRequest(**dict(row)) for row in rows]

    def update_request(self, request_id: str, **fields: Any) -> None:
        self._update("requests", "id", request_id, fields)

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

    # --- Messages d'un fil (une demande ou un besoin) -----------------------------------------

    def add_message(
        self,
        thread_id: str,
        sender_id: str,
        text: str,
        attachments: list[dict[str, Any]] | None = None,
        created_at: float | None = None,
    ) -> None:
        self._insert(
            "messages",
            {
                "id": _new_id(),
                "thread_id": thread_id,
                "sender_id": sender_id,
                "text": text,
                "attachments": json.dumps(attachments or []),
                "created_at": created_at or time.time(),
            },
        )

    def messages_of(self, thread_id: str) -> list[StoredMessage]:
        rows = self._run(
            "SELECT * FROM messages WHERE thread_id = ? ORDER BY created_at", (thread_id,)
        )
        return [
            StoredMessage(**{**dict(row), "attachments": json.loads(row["attachments"])})
            for row in rows
        ]

    def count_messages(self) -> int:
        return int(self._run("SELECT count(*) AS n FROM messages")[0]["n"])

    # --- Besoins publiés par les patients ------------------------------------------------------

    def add_need(self, patient_id: str, text: str) -> StoredNeed:
        need_id = _new_id()
        self._insert(
            "needs",
            {
                "id": need_id,
                "patient_id": patient_id,
                "text": text,
                "status": "open",
                "created_at": time.time(),
            },
        )
        need = self.need(need_id)
        assert need is not None
        return need

    def need(self, need_id: str) -> StoredNeed | None:
        rows = self._run("SELECT * FROM needs WHERE id = ?", (need_id,))
        return StoredNeed(**dict(rows[0])) if rows else None

    def needs(self, status: str | None = None) -> list[StoredNeed]:
        if status is None:
            rows = self._run("SELECT * FROM needs ORDER BY created_at")
        else:
            rows = self._run("SELECT * FROM needs WHERE status = ? ORDER BY created_at", (status,))
        return [StoredNeed(**dict(row)) for row in rows]

    def needs_of(self, role: str, user_id: str) -> list[StoredNeed]:
        column = "helper_id" if role == "helper" else "patient_id"
        rows = self._run(f"SELECT * FROM needs WHERE {column} = ? ORDER BY created_at", (user_id,))
        return [StoredNeed(**dict(row)) for row in rows]

    def update_need(self, need_id: str, **fields: Any) -> None:
        self._update("needs", "id", need_id, fields)

    # --- Notes des cliniciens --------------------------------------------------------------

    def note(self, patient_id: str) -> StoredNote | None:
        rows = self._run("SELECT * FROM clinician_notes WHERE patient_id = ?", (patient_id,))
        return StoredNote(**dict(rows[0])) if rows else None

    def save_note(self, patient_id: str, author_id: str, mood: str, proud: str, loves: str) -> None:
        self._run(
            "INSERT OR REPLACE INTO clinician_notes"
            " (patient_id, author_id, mood, proud, loves, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (patient_id, author_id, mood, proud, loves, time.time()),
        )

    # --- Messages envoyés à l'équipe -----------------------------------------------------------

    def add_feedback(self, **fields: Any) -> None:
        self._insert(
            "feedback", {"id": _new_id(), "created_at": time.time(), "resolved": 0, **fields}
        )

    def feedback(self) -> list[StoredFeedback]:
        rows = self._run("SELECT * FROM feedback ORDER BY created_at DESC")
        return [StoredFeedback(**{**dict(row), "resolved": bool(row["resolved"])}) for row in rows]

    def set_feedback_resolved(self, feedback_id: str, resolved: bool) -> bool:
        if not self._run("SELECT id FROM feedback WHERE id = ?", (feedback_id,)):
            return False
        self._update("feedback", "id", feedback_id, {"resolved": int(resolved)})
        return True
