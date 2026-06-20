"""
firms.py - Historical fire hotspots from NASA FIRMS (optional sanity check).

If FIRMS_API_KEY is set, we pull recent VIIRS hotspots for the bbox so the user
can eyeball whether the risk map points at places that have actually burned. No
key -> feature is simply disabled (the rest of the app is unaffected).

API: https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{SENSOR}/{W,S,E,N}/{days}
"""

from __future__ import annotations

import csv
import io
import json
import time

import requests

from backend import config
from backend.data.grid import Grid

_SENSOR = "VIIRS_SNPP_NRT"
_DAYS = 7
_TTL_S = 6 * 3600
_CACHE = config.CACHE_DIR / "firms.json"
_TIMEOUT = 25


def get_firepoints(grid: Grid, *, force_refresh: bool = False) -> dict:
    if not config.FIRMS_API_KEY:
        return {"enabled": False, "points": []}

    if _CACHE.exists() and not force_refresh:
        try:
            cached = json.loads(_CACHE.read_text())
            if (time.time() - cached.get("fetched_at", 0)) < _TTL_S:
                return cached
        except Exception:
            pass

    area = f"{grid.lon_min},{grid.lat_min},{grid.lon_max},{grid.lat_max}"
    url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
           f"{config.FIRMS_API_KEY}/{_SENSOR}/{area}/{_DAYS}")
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        points = _parse_csv(resp.text, grid)
        result = {"enabled": True, "fetched_at": time.time(), "sensor": _SENSOR,
                  "days": _DAYS, "points": points}
        _CACHE.write_text(json.dumps(result))
        return result
    except Exception as exc:
        if _CACHE.exists():
            return json.loads(_CACHE.read_text())
        return {"enabled": True, "points": [], "error": str(exc)}


def _parse_csv(text: str, grid: Grid) -> list[dict]:
    points = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except (KeyError, ValueError):
            continue
        if not grid.contains(lon, lat):
            continue
        points.append({
            "lat": lat, "lon": lon,
            "acq_date": row.get("acq_date"),
            "frp": _num(row.get("frp")),
            "confidence": row.get("confidence"),
        })
    return points


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
