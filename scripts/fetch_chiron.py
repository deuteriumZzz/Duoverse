"""Fetch Chiron's longitude table from the NASA JPL Horizons API (public domain): python scripts/fetch_chiron.py [out] [start] [stop].

DE421 has no Chiron, and Horizons writes small-body SPK files as type 21, which Skyfield cannot read. So we ask
Horizons for the geocentric apparent ecliptic longitude of date (quantity 31) once a day in TT and interpolate it
(Chiron moves under 0.15° a day, so the error stays under 0.001°). The default span matches DE421. Stdlib only.
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://ssd.jpl.nasa.gov/api/horizons.api"


def rows(start: str, stop: str, body: str = "'2060;'") -> list[str]:
    query = {
        "format": "json",
        "COMMAND": body,  # «;» = small-body search: 2060 Chiron, not the planet-ID list
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": "'500@399'",  # geocentre
        "START_TIME": f"'{start}'",
        "STOP_TIME": f"'{stop}'",
        "STEP_SIZE": "'1 d'",
        "TIME_TYPE": "TT",
        "QUANTITIES": "'31'",
        "CSV_FORMAT": "YES",
        "CAL_FORMAT": "JD",
        "OBJ_DATA": "NO",
    }
    with urllib.request.urlopen(f"{API}?{urllib.parse.urlencode(query)}", timeout=120) as r:
        text = json.load(r)["result"]
    if "$$SOE" not in text:
        raise SystemExit(f"Horizons gave no table:\n{text[:2000]}")
    out = []
    for line in text.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines():
        cols = [c.strip() for c in line.split(",")]
        out.append(f"{float(cols[0]):.1f} {float(cols[-3]):.4f}")  # JD (TT), ObsEcLon; the line ends with lat and ""
    return out


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/chiron.txt")
    start, stop = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("1900-01-01", "2053-10-01")
    first, last = int(start[:4]), int(stop[:4])
    lines = []
    for year in range(first, last + 1, 30):  # ~11k rows a request keeps each answer small
        lo = start if year == first else f"{year}-01-01"
        hi = stop if year + 30 > last else f"{year + 29}-12-31"
        lines += rows(lo, hi)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "# 2060 Chiron, JPL Horizons: JD (TT), geocentric apparent ecliptic longitude of date, degrees\n" + "\n".join(lines) + "\n"
    )
    print(f"{out}: {len(lines)} days")


if __name__ == "__main__":
    main()
