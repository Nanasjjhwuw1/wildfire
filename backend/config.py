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
# Chiang Mai province, Thailand. (lon_min, lat_min, lon_max, lat_max) in WGS84.
# ~1.4 x 3.0 deg (~150 x 335 km) — spans 4 WorldCover 3-deg tiles (mosaicked).
BBOX: tuple[float, float, float, float] = (
    float(os.getenv("BBOX_LON_MIN", 98.0)),
    float(os.getenv("BBOX_LAT_MIN", 17.3)),
    float(os.getenv("BBOX_LON_MAX", 99.4)),
    float(os.getenv("BBOX_LAT_MAX", 20.35)),
)

AREA_NAME = os.getenv("AREA_NAME", "Chiang Mai province")

# Target ground resolution of one grid cell, metres. ~1 km over the province
# gives a ~340 x 148 grid (~50k cells) that the CA can still run in reasonable
# time on a small free-tier instance.
CELL_SIZE_M: float = float(os.getenv("CELL_SIZE_M", 1000.0))

# DEM tile zoom (Terrarium). Coarser zoom = far fewer tiles for a large area.
# z10 ~= 150 m/px, plenty for a ~1 km grid.
TERRAIN_ZOOM: int = int(os.getenv("TERRAIN_ZOOM", 10))

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
    {"name": "เมืองเชียงใหม่", "lat": 18.7900, "lon": 98.9800},
    {"name": "ดอยสุเทพ", "lat": 18.8048, "lon": 98.9217},
    {"name": "ฝาง", "lat": 19.9200, "lon": 99.2100},
    {"name": "จอมทอง", "lat": 18.4200, "lon": 98.6700},
    {"name": "ดอยอินทนนท์", "lat": 18.5880, "lon": 98.4870},
]
