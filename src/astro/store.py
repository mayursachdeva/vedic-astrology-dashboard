"""Profile storage.

A local single-user dashboard holding a handful of family members does not need an ORM
or a migration framework, so this is plain sqlite3 with explicit SQL. Birth data never
leaves this file.

What a profile stores is deliberately more than a date and a place: the ayanamsa, node
convention and LMT decision are part of the chart's identity, and a reading is not
reproducible without them.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "astro.db"

# How sure we are of the recorded birth time. This drives the ascendant warning in the
# UI, so it is a stored fact rather than a note.
TIME_CONFIDENCE = ("exact", "to_the_minute", "to_the_hour", "approximate", "unknown")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    relation        TEXT    NOT NULL DEFAULT '',
    birth_local     TEXT    NOT NULL,
    place           TEXT    NOT NULL DEFAULT '',
    latitude        REAL    NOT NULL,
    longitude       REAL    NOT NULL,
    timezone_name   TEXT,
    use_true_lmt    INTEGER NOT NULL DEFAULT 0,
    time_confidence TEXT    NOT NULL DEFAULT 'to_the_minute',
    ayanamsa        TEXT    NOT NULL DEFAULT 'lahiri',
    node_type       TEXT    NOT NULL DEFAULT 'mean',
    house_system    TEXT    NOT NULL DEFAULT 'whole_sign',
    notes           TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL
);
"""


@dataclass(frozen=True)
class Profile:
    name: str
    birth_local: datetime
    latitude: float
    longitude: float
    relation: str = ""
    place: str = ""
    timezone_name: str | None = None
    use_true_lmt: bool = False
    time_confidence: str = "to_the_minute"
    ayanamsa: str = "lahiri"
    node_type: str = "mean"
    house_system: str = "whole_sign"
    notes: str = ""
    id: int | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("profile needs a name")
        if self.birth_local.tzinfo is not None:
            raise ValueError("birth_local must be naive — it is a wall clock reading")
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude {self.latitude} out of range")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude {self.longitude} out of range")
        if self.time_confidence not in TIME_CONFIDENCE:
            raise ValueError(
                f"time_confidence must be one of {TIME_CONFIDENCE}, "
                f"got {self.time_confidence!r}"
            )

    def as_dict(self) -> dict:
        data = asdict(self)
        data["birth_local"] = self.birth_local.isoformat()
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        return data


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the database, creating the file and schema if needed."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(_SCHEMA)
    return connection


def _to_profile(row: sqlite3.Row) -> Profile:
    return Profile(
        id=row["id"],
        name=row["name"],
        relation=row["relation"],
        birth_local=datetime.fromisoformat(row["birth_local"]),
        place=row["place"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        timezone_name=row["timezone_name"],
        use_true_lmt=bool(row["use_true_lmt"]),
        time_confidence=row["time_confidence"],
        ayanamsa=row["ayanamsa"],
        node_type=row["node_type"],
        house_system=row["house_system"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def create_profile(connection: sqlite3.Connection, profile: Profile) -> Profile:
    created_at = profile.created_at or datetime.now()
    cursor = connection.execute(
        """
        INSERT INTO profiles (
            name, relation, birth_local, place, latitude, longitude, timezone_name,
            use_true_lmt, time_confidence, ayanamsa, node_type, house_system, notes,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile.name,
            profile.relation,
            profile.birth_local.isoformat(),
            profile.place,
            profile.latitude,
            profile.longitude,
            profile.timezone_name,
            int(profile.use_true_lmt),
            profile.time_confidence,
            profile.ayanamsa,
            profile.node_type,
            profile.house_system,
            profile.notes,
            created_at.isoformat(),
        ),
    )
    connection.commit()
    return replace(profile, id=cursor.lastrowid, created_at=created_at)


def list_profiles(connection: sqlite3.Connection) -> list[Profile]:
    rows = connection.execute("SELECT * FROM profiles ORDER BY id").fetchall()
    return [_to_profile(row) for row in rows]


def get_profile(connection: sqlite3.Connection, profile_id: int) -> Profile:
    row = connection.execute(
        "SELECT * FROM profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"no profile with id {profile_id}")
    return _to_profile(row)


def update_profile(connection: sqlite3.Connection, profile: Profile) -> Profile:
    if profile.id is None:
        raise ValueError("cannot update a profile that has no id")
    connection.execute(
        """
        UPDATE profiles SET
            name = ?, relation = ?, birth_local = ?, place = ?, latitude = ?,
            longitude = ?, timezone_name = ?, use_true_lmt = ?, time_confidence = ?,
            ayanamsa = ?, node_type = ?, house_system = ?, notes = ?
        WHERE id = ?
        """,
        (
            profile.name,
            profile.relation,
            profile.birth_local.isoformat(),
            profile.place,
            profile.latitude,
            profile.longitude,
            profile.timezone_name,
            int(profile.use_true_lmt),
            profile.time_confidence,
            profile.ayanamsa,
            profile.node_type,
            profile.house_system,
            profile.notes,
            profile.id,
        ),
    )
    connection.commit()
    return get_profile(connection, profile.id)


def delete_profile(connection: sqlite3.Connection, profile_id: int) -> None:
    cursor = connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    connection.commit()
    if cursor.rowcount == 0:
        raise KeyError(f"no profile with id {profile_id}")
