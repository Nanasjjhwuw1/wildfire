"""
aoi.py - Clip overlays to the real Chiang Mai province boundary.

The study grid is a rectangular bbox, but the province is an irregular shape.
We rasterise the vendored province polygon (``backend/assets/chiangmai.geojson``,
from geoBoundaries ADM1) onto the grid so map overlays can be made transparent
outside the province, and serve the polygon itself so the frontend can draw the
real border instead of the bbox rectangle.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

from backend import config
from backend.data.grid import Grid

_GEOJSON = pathlib.Path(__file__).resolve().parents[1] / "assets" / "chiangmai.geojson"


def province_geojson() -> dict | None:
    """The vendored province boundary as a GeoJSON FeatureCollection (or None)."""
    try:
        return json.loads(_GEOJSON.read_text(encoding="utf-8"))
    except Exception:
        return None


def _inside_mask(grid: Grid) -> np.ndarray:
    """Rasterise the province polygon onto the grid (True = inside the province)."""
    gj = province_geojson()
    if gj is None:
        return np.ones(grid.shape, dtype=bool)  # no polygon -> don't clip anything
    try:
        from rasterio.features import rasterize
        from rasterio.transform import Affine

        geoms = [(f.get("geometry", f), 1)
                 for f in gj.get("features", [gj]) if f.get("geometry")]
        mask = rasterize(geoms, out_shape=grid.shape, transform=Affine(*grid.affine()),
                         fill=0, all_touched=True, dtype="uint8")
        return mask.astype(bool)
    except Exception:
        return np.ones(grid.shape, dtype=bool)


def outside_mask(grid: Grid) -> np.ndarray:
    """Boolean grid, True for cells OUTSIDE the province (to hide on overlays).

    Cached to ``.npy``. In mock mode there's no real geography, so nothing is
    clipped (keeps tests independent of the vendored polygon).
    """
    if config.DATA_MODE == "mock":
        return np.zeros(grid.shape, dtype=bool)
    cache = config.CACHE_DIR / f"aoi_outside_{grid.n_rows}x{grid.n_cols}.npy"
    if cache.exists():
        return np.load(cache)
    out = ~_inside_mask(grid)
    try:
        np.save(cache, out)
    except Exception:
        pass
    return out
