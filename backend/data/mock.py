"""
mock.py - Synthetic data for offline development ONLY (DATA_MODE=mock).

Produces the same shapes the real loaders return, so the whole pipeline (risk,
simulate, recommend, API, frontend) runs with no network. NEVER the default -
real data is the default; this exists so you can hack on a plane.
"""

from __future__ import annotations

import time

import numpy as np

from backend.data.grid import Grid


def mock_weather(grid: Grid) -> dict:
    rep = {"temp": 34.0, "rh": 28.0, "wind_speed": 6.0, "wind_dir": 225.0, "rain_24h": 0.0}
    pts = []
    for lat, lon in [
        (grid.lat_max, grid.lon_min),
        (grid.lat_max, grid.lon_max),
        (grid.lat_min, grid.lon_min),
        (grid.lat_min, grid.lon_max),
        (grid.mid_lat, (grid.lon_min + grid.lon_max) / 2),
    ]:
        pts.append({"lat": lat, "lon": lon, "temp": 34.0, "rh": 28.0,
                    "wind_speed": 6.0, "wind_dir": 225.0, "precip_now": 0.0, "rain_24h": 0.0})
    return {"fetched_at": time.time(), "source": "mock", "representative": rep, "points": pts}


def mock_terrain(grid: Grid) -> dict:
    """A synthetic ridge so slope effects are visible."""
    nr, nc = grid.shape
    yy, xx = np.mgrid[0:nr, 0:nc]
    elevation = (
        500.0
        + 600.0 * np.exp(-(((xx - nc * 0.55) ** 2 + (yy - nr * 0.38) ** 2) / (2 * (nc * 0.22) ** 2)))
        + 80.0 * np.sin(xx / 7.0)
    )
    from backend.data.terrain import _derive

    return _derive(grid, elevation)


def mock_fuel(grid: Grid) -> dict:
    """Synthetic land cover: forest band, grassland, a river + built-up patch."""
    nr, nc = grid.shape
    yy, xx = np.mgrid[0:nr, 0:nc]
    classes = np.full((nr, nc), 30, dtype=np.int16)         # grassland baseline
    classes[: int(nr * 0.45), :] = 10                       # tree cover in the north
    classes[int(nr * 0.45) : int(nr * 0.6), :] = 20         # shrub band
    classes[np.abs((xx - yy) - int(nc * 0.1)) <= 1] = 80    # diagonal river (water)
    classes[int(nr * 0.8) :, int(nc * 0.6) : int(nc * 0.7)] = 50  # built-up patch
    from backend.data.fuel import classes_to_fuel

    return classes_to_fuel(classes)
