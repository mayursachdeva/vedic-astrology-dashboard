"""Looking up a birth place by name, offline.

Typing coordinates by hand is the most error-prone part of entering a chart, and a wrong
sign or a transposed digit moves the lagna without looking obviously wrong. So the place
is searched by name instead.

The lookup runs entirely on this machine. Sending "born in <village>" to a geocoding
service would leak the one detail that, next to a birth date, identifies a person, and
the whole project exists so that does not happen.

Two tiers, both local:

- `geonamescache`, bundled: about 34,000 places worldwide over roughly 15,000 people.
  Enough for cities, not for villages, and cheap enough to hold in memory.
- An indexed SQLite gazetteer built from GeoNames country dumps by
  `scripts/fetch_places.py`, which reaches individual hamlets. India alone is 548,000
  places; holding those as objects cost a gigabyte of memory and made each search take
  nearly two seconds, so they live in a file with an index on the folded name and are
  queried rather than loaded.
"""

from __future__ import annotations

import functools
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
PLACES_DB = DATA_DIR / "places.db"
DUMPS_DIR = DATA_DIR / "places"

# GeoNames feature codes worth offering: populated places and the seats of
# administrative divisions. Everything else is rivers, farms and spot heights.
POPULATED_FEATURES = frozenset(
    {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "PPLS", "PPLX"}
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
    name       TEXT NOT NULL,
    folded     TEXT NOT NULL,
    admin      TEXT NOT NULL DEFAULT '',
    country    TEXT NOT NULL DEFAULT '',
    latitude   REAL NOT NULL,
    longitude  REAL NOT NULL,
    timezone   TEXT NOT NULL DEFAULT '',
    population INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS places_folded ON places(folded);
CREATE INDEX IF NOT EXISTS places_population ON places(population DESC);
"""


@dataclass(frozen=True)
class Place:
    name: str
    country: str
    admin: str
    latitude: float
    longitude: float
    timezone: str
    population: int

    @property
    def label(self) -> str:
        parts = [self.name]
        # A bare GeoNames admin1 code — "16" for Maharashtra — tells a reader nothing,
        # so it is shown only once resolved to a name.
        if self.admin and not self.admin.isdigit():
            parts.append(self.admin)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "admin": self.admin,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "population": self.population,
        }


def fold(text: str) -> str:
    """Lowercase, strip accents and punctuation.

    Place names are transliterated inconsistently — Bengaluru and Bengalūru, Puduchcheri
    and Puducherry — so matching has to ignore what the spellings disagree about.
    """
    stripped = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in stripped if not unicodedata.combining(c))
    return " ".join(
        "".join(c if c.isalnum() or c.isspace() else " " for c in plain).lower().split()
    )


# --- the in-memory tier ------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _bundled() -> list[tuple[str, Place]]:
    try:
        import geonamescache
    except ImportError:  # pragma: no cover - a declared dependency
        return []

    cache = geonamescache.GeonamesCache()
    countries = {code: data["name"] for code, data in cache.get_countries().items()}
    places = []
    for city in cache.get_cities().values():
        place = Place(
            name=city["name"],
            country=countries.get(city["countrycode"], city["countrycode"]),
            admin="",
            latitude=float(city["latitude"]),
            longitude=float(city["longitude"]),
            timezone=city["timezone"],
            population=int(city["population"] or 0),
        )
        places.append((fold(place.name), place))
    return places


# --- the indexed tier --------------------------------------------------------


def build_database(
    dumps: Path | str = DUMPS_DIR,
    database: Path | str = PLACES_DB,
    admin_names: dict[str, str] | None = None,
) -> int:
    """Index GeoNames dumps into SQLite. Returns how many places were written."""
    dumps, database = Path(dumps), Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists():
        database.unlink()

    connection = sqlite3.connect(database)
    connection.executescript(SCHEMA)
    admin_names = admin_names or {}
    written = 0

    for path in sorted(dumps.glob("*.txt")):
        rows = []
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                fields = line.split("\t")
                if len(fields) < 18 or fields[7] not in POPULATED_FEATURES:
                    continue
                try:
                    latitude, longitude = float(fields[4]), float(fields[5])
                except ValueError:
                    continue
                country_code = fields[8]
                admin_code = fields[10] or ""
                rows.append(
                    (
                        fields[1],
                        fold(fields[1]),
                        admin_names.get(f"{country_code}.{admin_code}", admin_code),
                        country_code,
                        latitude,
                        longitude,
                        fields[17].strip(),
                        int(fields[14] or 0),
                    )
                )
        connection.executemany(
            "INSERT INTO places (name, folded, admin, country, latitude, longitude,"
            " timezone, population) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        written += len(rows)

    connection.commit()
    connection.close()
    return written


@functools.lru_cache(maxsize=4)
def _connect(database: str) -> sqlite3.Connection | None:
    if not Path(database).exists():
        return None
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _row_to_place(row: sqlite3.Row, countries: dict[str, str]) -> Place:
    return Place(
        name=row["name"],
        country=countries.get(row["country"], row["country"]),
        admin=row["admin"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        timezone=row["timezone"],
        population=row["population"],
    )


@functools.lru_cache(maxsize=1)
def _country_names() -> dict[str, str]:
    try:
        import geonamescache
    except ImportError:  # pragma: no cover
        return {}
    return {
        code: data["name"]
        for code, data in geonamescache.GeonamesCache().get_countries().items()
    }


# --- search ------------------------------------------------------------------


def search(query: str, limit: int = 8, database: Path | str = PLACES_DB) -> list[Place]:
    """Places matching a typed name, best first.

    Ranked by how closely the name matches and then by population, because someone
    typing "Delhi" means the city of eleven million rather than the cantonment. A
    trailing state or country — "Nashik, Maharashtra" — narrows the search; if nothing
    matches that context the results are still shown, since a misspelled state should
    not hide the town.
    """
    parts = [fold(part) for part in query.split(",") if fold(part)]
    if not parts or len(parts[0]) < 2:
        return []
    name, context = parts[0], parts[1:]

    candidates: list[tuple[int, Place]] = []

    connection = _connect(str(database))
    if connection is not None:
        countries = _country_names()
        # Three passes rather than one LIKE '%x%': the exact and prefix forms use the
        # index and answer instantly, and the scan only runs if they came up short.
        queries = (
            (0, "folded = ?", (name,)),
            (1, "folded LIKE ? AND folded <> ?", (f"{name}%", name)),
            (2, "folded LIKE ?", (f"%{name}%",)),
        )
        for rank, where, params in queries:
            if len(candidates) >= limit * 6:
                break
            rows = connection.execute(
                f"SELECT * FROM places WHERE {where} ORDER BY population DESC LIMIT ?",
                (*params, limit * 6),
            ).fetchall()
            candidates.extend((rank, _row_to_place(row, countries)) for row in rows)

    for folded, place in _bundled():
        if folded == name:
            candidates.append((0, place))
        elif folded.startswith(name):
            candidates.append((1, place))
        elif name in folded:
            candidates.append((2, place))

    scored = []
    for rank, place in candidates:
        matched = True
        if context:
            haystack = fold(f"{place.admin} {place.country}")
            matched = all(hint in haystack for hint in context)
        scored.append(((rank + (0 if matched else 10), -place.population), place, matched))

    if context and any(entry[2] for entry in scored):
        scored = [entry for entry in scored if entry[2]]
    scored.sort(key=lambda entry: entry[0])

    seen: set[tuple] = set()
    results: list[Place] = []
    for _, place, _matched in scored:
        key = (fold(place.name), round(place.latitude, 2), round(place.longitude, 2))
        if key in seen:
            continue
        seen.add(key)
        results.append(place)
        if len(results) >= limit:
            break
    return results


def coverage(database: Path | str = PLACES_DB) -> dict:
    """What the gazetteer knows, so the interface can say when it is thin."""
    connection = _connect(str(database))
    indexed = 0
    countries: list[str] = []
    if connection is not None:
        indexed = connection.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        countries = [
            row[0]
            for row in connection.execute(
                "SELECT country FROM places GROUP BY country ORDER BY COUNT(*) DESC"
            )
        ]
    return {
        "bundled": len(_bundled()),
        "indexed": indexed,
        "countries_indexed": countries,
        "total": len(_bundled()) + indexed,
    }
