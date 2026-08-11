"""Download GeoNames country dumps for village-level place lookup.

The bundled gazetteer only covers places above roughly 15,000 people, which misses the
villages a lot of birth certificates name. GeoNames publishes a free dump per country
that goes down to individual hamlets.

This is the only part of the project that touches the network, it is run by hand, and
it sends nothing at all about anyone — it fetches a public file. Afterwards place lookup
is offline again.

    uv run python scripts/fetch_places.py IN        # India, about 3 MB
    uv run python scripts/fetch_places.py IN US GB

Country codes: https://download.geonames.org/export/dump/
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import httpx

BASE = "https://download.geonames.org/export/dump"
DESTINATION = Path(__file__).resolve().parent.parent / "data" / "places"


def fetch_admin_names() -> dict[str, str]:
    """admin1CodesASCII.txt maps "IN.16" to "Maharashtra".

    Without it the dumps carry bare numeric codes, so "Nashik, Maharashtra" cannot be
    narrowed by its state and the label has nothing readable to show.
    """
    url = f"{BASE}/admin1CodesASCII.txt"
    print(f"fetching {url}")
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    names = {}
    for line in response.text.splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            names[fields[0]] = fields[1]
    print(f"  {len(names):,} administrative divisions")
    return names


def fetch(code: str) -> Path:
    code = code.upper()
    url = f"{BASE}/{code}.zip"
    print(f"fetching {url}")

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    DESTINATION.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        member = f"{code}.txt"
        if member not in archive.namelist():
            raise RuntimeError(f"{member} not found in the archive for {code}")
        target = DESTINATION / member
        target.write_bytes(archive.read(member))

    lines = sum(1 for _ in target.open(encoding="utf-8", errors="replace"))
    print(f"  saved {target} ({lines:,} rows, {target.stat().st_size / 1e6:.1f} MB)")
    return target


def main() -> None:
    codes = sys.argv[1:] or ["IN"]
    for code in codes:
        try:
            fetch(code)
        except Exception as error:
            print(f"  failed for {code}: {error}", file=sys.stderr)

    admin_names = {}
    try:
        admin_names = fetch_admin_names()
    except Exception as error:
        print(f"  could not fetch state names: {error}", file=sys.stderr)

    from astro.core.places import build_database, coverage

    print("indexing into SQLite...")
    written = build_database(admin_names=admin_names)
    summary = coverage()
    print(f"  indexed {written:,} places")
    print(
        f"gazetteer holds {summary['total']:,} places "
        f"({summary['bundled']:,} bundled + {summary['indexed']:,} indexed)"
    )


if __name__ == "__main__":
    main()
