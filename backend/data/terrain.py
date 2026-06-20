"""
terrain.py - Real elevation from AWS Terrain Tiles (no auth) -> slope & aspect.

AWS hosts global "Terrarium" PNG terrain tiles (a blend of SRTM, ASTER, NED,
...). Elevation is RGB-encoded:

    elevation_m = (R * 256 + G + B / 256) - 32768

We download the few web-mercator tiles covering the bbox (cached to disk as
PNGs), decode them with numpy/Pillow (no GDAL needed for the DEM), mosaic them,
then bilinearly sample onto the master grid. Slope and aspect are computed from
the gridded elevation with the real cell sizes.

Tiles: https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png
"""

from __future__ import annotations

import math

import numpy as np
import requests
from PIL import Image

from backend import config
from backend.data.grid import Grid

_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
_ZOOM = 12          # ~36 m/px at 19N -> finer than the 100 m grid
_TILE_PX = 256
_TIMEOUT = 30
_TILE_DIR = config.CACHE_DIR / "terrain_tiles"
_TILE_DIR.mkdir(parents=True, exist_ok=True)


def _lonlat_to_global_px(lon: float, lat: float, z: int) -> tuple[float, float]:
    """Web-mercator global pixel coordinates at zoom z (slippy-map math)."""
    lat_r = math.radians(lat)
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n * _TILE_PX
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n * _TILE_PX
    return x, y


def _fetch_tile(z: int, x: int, y: int) -> np.ndarray:
    """Return an (H, W, 3) uint8 tile, cached on disk."""
    path = _TILE_DIR / f"{z}_{x}_{y}.png"
    if not path.exists():
        url = _TILE_URL.format(z=z, x=x, y=y)
        resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "wildfire-mvp/1.0"})
        resp.raise_for_status()
        path.write_bytes(resp.content)
    img = Image.open(path).convert("RGB")
    return np.asarray(img, dtype=np.float64)


def _decode_elevation(rgb: np.ndarray) -> np.ndarray:
    """Terrarium RGB -> metres."""
    return (rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0) - 32768.0


def _elevation_mosaic(grid: Grid, z: int = _ZOOM) -> tuple[np.ndarray, int, int]:
    """Build an elevation mosaic covering the bbox; return (elev, px0, py0)."""
    # pixel extents of the bbox at this zoom
    gx0, gy0 = _lonlat_to_global_px(grid.lon_min, grid.lat_max, z)  # top-left
    gx1, gy1 = _lonlat_to_global_px(grid.lon_max, grid.lat_min, z)  # bottom-right
    tx0, ty0 = int(gx0 // _TILE_PX), int(gy0 // _TILE_PX)
    tx1, ty1 = int(gx1 // _TILE_PX), int(gy1 // _TILE_PX)

    rows = []
    for ty in range(ty0, ty1 + 1):
        cols = [_decode_elevation(_fetch_tile(z, tx, ty)) for tx in range(tx0, tx1 + 1)]
        rows.append(np.hstack(cols))
    mosaic = np.vstack(rows)
    return mosaic, tx0 * _TILE_PX, ty0 * _TILE_PX


def _sample_to_grid(grid: Grid, mosaic: np.ndarray, px0: int, py0: int, z: int) -> np.ndarray:
    """Bilinearly sample the mosaic at each grid cell centre."""
    lons = grid.cell_lons()
    lats = grid.cell_lats()
    lon2d, lat2d = np.meshgrid(lons, lats)

    n = 2 ** z
    # vectorised lon/lat -> global pixel
    gx = (lon2d + 180.0) / 360.0 * n * _TILE_PX - px0
    lat_r = np.radians(lat2d)
    gy = (1.0 - np.arcsinh(np.tan(lat_r)) / math.pi) / 2.0 * n * _TILE_PX - py0

    h, w = mosaic.shape
    x0 = np.clip(np.floor(gx).astype(int), 0, w - 2)
    y0 = np.clip(np.floor(gy).astype(int), 0, h - 2)
    fx = np.clip(gx - x0, 0, 1)
    fy = np.clip(gy - y0, 0, 1)

    v00 = mosaic[y0, x0]
    v10 = mosaic[y0, x0 + 1]
    v01 = mosaic[y0 + 1, x0]
    v11 = mosaic[y0 + 1, x0 + 1]
    top = v00 * (1 - fx) + v10 * fx
    bot = v01 * (1 - fx) + v11 * fx
    return top * (1 - fy) + bot * fy


def get_terrain(grid: Grid, *, force_refresh: bool = False, zoom: int | None = None) -> dict:
    """Return {elevation, slope_deg, aspect_deg} on the master grid (n_rows,n_cols).

    Cached as a single ``.npy`` so repeat calls (and offline demos) are instant.
    ``zoom`` defaults to ``config.TERRAIN_ZOOM``; pass a value to override (the ML
    scripts use a coarser zoom for very large regions with far fewer tiles).
    """
    if config.DATA_MODE == "mock":
        from backend.data import mock

        return mock.mock_terrain(grid)

    if zoom is None:
        zoom = config.TERRAIN_ZOOM

    cache = config.CACHE_DIR / f"terrain_{grid.n_rows}x{grid.n_cols}_z{zoom}.npy"
    if cache.exists() and not force_refresh:
        elevation = np.load(cache)
    else:
        mosaic, px0, py0 = _elevation_mosaic(grid, zoom)
        elevation = _sample_to_grid(grid, mosaic, px0, py0, zoom)
        np.save(cache, elevation)

    return _derive(grid, elevation)


def _derive(grid: Grid, elevation: np.ndarray) -> dict:
    """Slope (degrees) and aspect (degrees from north, clockwise) from elevation."""
    # gradient with real ground spacing; rows go south so dz/dy uses cell_height
    dz_dy, dz_dx = np.gradient(elevation, grid.cell_height_m, grid.cell_width_m)
    slope_deg = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    # aspect: compass direction the slope faces (0=N, 90=E, ...). +x=east, +y=south.
    aspect = np.degrees(np.arctan2(dz_dx, dz_dy))  # rough; refined below
    aspect = (90.0 - np.degrees(np.arctan2(-dz_dy, dz_dx))) % 360.0
    return {"elevation": elevation, "slope_deg": slope_deg, "aspect_deg": aspect}


if __name__ == "__main__":
    g = Grid.from_config()
    t = get_terrain(g)
    e = t["elevation"]
    print(f"elevation: {e.min():.0f}..{e.max():.0f} m  mean {e.mean():.0f} m")
    print(f"slope    : {t['slope_deg'].min():.1f}..{t['slope_deg'].max():.1f} deg")
