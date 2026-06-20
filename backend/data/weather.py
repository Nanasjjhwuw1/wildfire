"""
weather.py - Live weather from Open-Meteo (free, no API key) + disk cache.

We fetch *current* conditions at the four bbox corners (plus the centre for a
representative reading) in a single Open-Meteo call, then bilinearly
interpolate temperature and humidity onto the master grid so the risk map has
real spatial structure. Wind is taken as the area-mean vector (the CA assumes
one uniform wind field).

Caching: results are written to ``cache/weather.json`` and reused while fresh
(``WEATHER_TTL_S``). If a refresh fails but a stale cache exists, we fall back
to it so a demo keeps working without network. ``DATA_MODE=mock`` bypasses the
network entirely.
"""

from __future__ import annotations

import json
import math
import time

import numpy as np
import requests

from backend import config
from backend.data.grid import Grid

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_CACHE_FILE = config.CACHE_DIR / "weather.json"
_TIMEOUT = 20


def _corner_points(grid: Grid) -> list[tuple[float, float]]:
    """(lat, lon) for the 4 corners + centre of the grid."""
    return [
        (grid.lat_max, grid.lon_min),  # NW
        (grid.lat_max, grid.lon_max),  # NE
        (grid.lat_min, grid.lon_min),  # SW
        (grid.lat_min, grid.lon_max),  # SE
        (grid.mid_lat, (grid.lon_min + grid.lon_max) / 2.0),  # centre
    ]


def _rain_last_24h(hourly: dict, current_time: str) -> float:
    """Sum the 24 hourly precipitation values up to the current hour (mm)."""
    times = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    if not times or not precip:
        return 0.0
    try:
        idx = times.index(current_time[:13] + ":00") if len(current_time) >= 13 else len(times) - 1
    except ValueError:
        idx = len(times) - 1
    lo = max(0, idx - 23)
    vals = [p for p in precip[lo : idx + 1] if p is not None]
    return float(sum(vals))


def _fetch_open_meteo(points: list[tuple[float, float]]) -> list[dict]:
    """One Open-Meteo request for several coordinates; returns a list of dicts."""
    lats = ",".join(f"{lat:.5f}" for lat, _ in points)
    lons = ",".join(f"{lon:.5f}" for _, lon in points)
    params = {
        "latitude": lats,
        "longitude": lons,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation",
        "hourly": "precipitation",
        "past_days": 1,
        "forecast_days": 1,
        "wind_speed_unit": "ms",  # m/s for the CA; converted to km/h for FWI
        "timezone": "auto",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    blocks = data if isinstance(data, list) else [data]  # multi-coord -> list

    out = []
    for blk in blocks:
        cur = blk.get("current", {})
        out.append(
            {
                "lat": blk.get("latitude"),
                "lon": blk.get("longitude"),
                "temp": cur.get("temperature_2m"),
                "rh": cur.get("relative_humidity_2m"),
                "wind_speed": cur.get("wind_speed_10m"),       # m/s
                "wind_dir": cur.get("wind_direction_10m"),     # deg, meteorological
                "precip_now": cur.get("precipitation"),
                "rain_24h": _rain_last_24h(blk.get("hourly", {}), cur.get("time", "")),
            }
        )
    return out


def _representative(points: list[dict]) -> dict:
    """Area-mean conditions. Wind is averaged as a vector (direction is circular)."""
    temps = [p["temp"] for p in points if p["temp"] is not None]
    rhs = [p["rh"] for p in points if p["rh"] is not None]
    rains = [p["rain_24h"] for p in points if p["rain_24h"] is not None]
    # vector mean of wind
    us, vs = [], []
    for p in points:
        if p["wind_speed"] is None or p["wind_dir"] is None:
            continue
        blow = math.radians((p["wind_dir"] + 180.0) % 360.0)
        us.append(p["wind_speed"] * math.sin(blow))
        vs.append(p["wind_speed"] * math.cos(blow))
    if us:
        u, v = float(np.mean(us)), float(np.mean(vs))
        wind_speed = math.hypot(u, v)
        blow_dir = (math.degrees(math.atan2(u, v))) % 360.0
        wind_dir = (blow_dir + 180.0) % 360.0  # back to meteorological "from"
    else:
        wind_speed, wind_dir = 0.0, 0.0
    return {
        "temp": float(np.mean(temps)) if temps else 25.0,
        "rh": float(np.mean(rhs)) if rhs else 50.0,
        "wind_speed": round(wind_speed, 2),
        "wind_dir": round(wind_dir, 1),
        "rain_24h": float(np.mean(rains)) if rains else 0.0,
    }


def get_area_weather(grid: Grid, *, force_refresh: bool = False) -> dict:
    """Return current weather for the area, cached on disk.

    Shape: {fetched_at, source, representative:{temp,rh,wind_speed,wind_dir,
            rain_24h}, points:[...]}.
    """
    if config.DATA_MODE == "mock":
        from backend.data import mock

        return mock.mock_weather(grid)

    # 1) fresh cache?
    cached = None
    if _CACHE_FILE.exists():
        try:
            cached = json.loads(_CACHE_FILE.read_text())
            if not force_refresh and (time.time() - cached.get("fetched_at", 0)) < config.WEATHER_TTL_S:
                cached["source"] = "cache"
                return cached
        except Exception:
            cached = None

    # 2) fetch fresh
    try:
        points = _fetch_open_meteo(_corner_points(grid))
        result = {
            "fetched_at": time.time(),
            "source": "open-meteo",
            "representative": _representative(points),
            "points": points,
        }
        _CACHE_FILE.write_text(json.dumps(result, indent=2))
        return result
    except Exception as exc:
        # 3) network failed -> stale cache beats nothing
        if cached is not None:
            cached["source"] = "stale-cache"
            cached["warning"] = f"refresh failed: {exc}"
            return cached
        raise RuntimeError(f"weather fetch failed and no cache available: {exc}") from exc


def weather_to_grid(grid: Grid, wx: dict) -> dict:
    """Interpolate point weather onto the full grid.

    Temperature and relative humidity are bilinearly interpolated from the 4
    corners; wind and 24 h rain are taken as area-representative scalars.
    Returns 2-D arrays (temp_c, rh) and scalars (wind_speed, wind_dir, rain_24h).
    """
    pts = wx["points"]
    rep = wx["representative"]

    def corner(lat_hi: bool, lon_lo: bool, key: str) -> float:
        """Pick the corner point matching (north?/west?) and read `key`."""
        target_lat = grid.lat_max if lat_hi else grid.lat_min
        target_lon = grid.lon_min if lon_lo else grid.lon_max
        best = min(pts, key=lambda p: abs(p["lat"] - target_lat) + abs(p["lon"] - target_lon))
        val = best.get(key)
        return float(val) if val is not None else (rep["temp"] if key == "temp" else rep["rh"])

    nr, nc = grid.shape
    u = (np.arange(nc) + 0.5) / nc          # west(0) -> east(1)
    v = (np.arange(nr) + 0.5) / nr          # north(0) -> south(1)
    uu, vv = np.meshgrid(u, v)

    def bilinear(key: str) -> np.ndarray:
        nw = corner(True, True, key)
        ne = corner(True, False, key)
        sw = corner(False, True, key)
        se = corner(False, False, key)
        return (
            nw * (1 - uu) * (1 - vv)
            + ne * uu * (1 - vv)
            + sw * (1 - uu) * vv
            + se * uu * vv
        )

    return {
        "temp_c": bilinear("temp"),
        "rh": np.clip(bilinear("rh"), 1.0, 100.0),
        "wind_speed": rep["wind_speed"],
        "wind_dir": rep["wind_dir"],
        "rain_24h": rep["rain_24h"],
    }
