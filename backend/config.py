"""
config.py - Single source of truth for the study area, grid, data mode, paths.

Everything geographic keys off BBOX + CELL_SIZE_M. Change BBOX to move the app
to a different area; the grid dimensions are derived so cells stay ~CELL_SIZE_M
on the ground.
"""

from __future__ import annotations

import math
import os
import pathlib

# Optional .env support (python-dotenv is added in Slice 2's requirements).
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv not installed yet during Slice 1
    pass


# --- study area ------------------------------------------------------------
# Doi Suthep, Chiang Mai. (lon_min, lat_min, lon_max, lat_max) in WGS84.
# ~0.10 deg square ~= 10.5 x 11.1 km on the ground.
BBOX: tuple[float, float, float, float] = (
    float(os.getenv("BBOX_LON_MIN", 98.85)),
    float(os.getenv("BBOX_LAT_MIN", 18.74)),
    float(os.getenv("BBOX_LON_MAX", 98.95)),
    float(os.getenv("BBOX_LAT_MAX", 18.84)),
)

AREA_NAME = os.getenv("AREA_NAME", "Doi Suthep, Chiang Mai")

# Target ground resolution of one grid cell, metres. The user picked ~100 m,
# giving roughly a 111 x 105 grid for the default bbox.
CELL_SIZE_M: float = float(os.getenv("CELL_SIZE_M", 100.0))

_M_PER_DEG_LAT = 111_320.0  # metres per degree latitude (good enough near 19N)


def _grid_dims(bbox: tuple[float, float, float, float], cell_m: float) -> tuple[int, int]:
    """Derive (n_rows, n_cols) so each cell is ~cell_m on the ground."""
    lon0, lat0, lon1, lat1 = bbox
    mid_lat = math.radians((lat0 + lat1) / 2.0)
    width_m = (lon1 - lon0) * _M_PER_DEG_LAT * math.cos(mid_lat)
    height_m = (lat1 - lat0) * _M_PER_DEG_LAT
    n_cols = max(1, round(width_m / cell_m))
    n_rows = max(1, round(height_m / cell_m))
    return n_rows, n_cols


GRID_ROWS, GRID_COLS = _grid_dims(BBOX, CELL_SIZE_M)


# --- data mode -------------------------------------------------------------
# "real" (default) pulls live data from Open-Meteo / terrain tiles / WorldCover.
# "mock" uses synthetic fields for offline dev ONLY.
DATA_MODE = os.getenv("DATA_MODE", "real").lower()

# NASA FIRMS map key (optional) - enables historical hotspot overlay if set.
FIRMS_API_KEY = os.getenv("FIRMS_API_KEY", "").strip()


# --- paths -----------------------------------------------------------------
BACKEND_DIR = pathlib.Path(__file__).resolve().parent
CACHE_DIR = pathlib.Path(os.getenv("CACHE_DIR", BACKEND_DIR / "cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# How long cached weather stays fresh before we re-fetch (seconds).
WEATHER_TTL_S = int(os.getenv("WEATHER_TTL_S", 3600))


# --- Monte-Carlo simulation defaults --------------------------------------
DEFAULT_N_RUNS = int(os.getenv("DEFAULT_N_RUNS", 30))
DEFAULT_N_STEPS = int(os.getenv("DEFAULT_N_STEPS", 60))
MAX_N_RUNS = int(os.getenv("MAX_N_RUNS", 80))
MAX_N_STEPS = int(os.getenv("MAX_N_STEPS", 150))


# --- assets to protect (used by the recommender) ---------------------------
# Communities / key points inside the bbox. Edit freely; coordinates are WGS84.
ASSETS: list[dict] = [
    {"name": "Wat Phra That Doi Suthep", "lat": 18.8048, "lon": 98.9217},
    {"name": "Doi Pui Hmong Village", "lat": 18.7950, "lon": 98.8950},
    {"name": "Mae Hia foothill community", "lat": 18.7550, "lon": 98.9200},
]
