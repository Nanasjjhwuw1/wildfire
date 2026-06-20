"""
fuel.py - Fuel map from ESA WorldCover 2021 (10 m land cover, no auth).

ESA WorldCover is published as Cloud-Optimized GeoTIFFs in a public AWS bucket,
tiled on a 3-degree grid named by the SW corner (e.g. N18E096 covers lat 18-21,
lon 96-99). We open the relevant COG over HTTPS and read ONLY the bbox window,
downsampled (nearest-neighbour, because classes are categorical) onto the
master grid - so we never download the whole multi-GB tile.

Each land-cover class maps to:
  * a fuel factor (>1 burns easier, <1 harder), and
  * a non-flammable flag (water / built-up / snow cannot burn).

Reference: ESA WorldCover v200 product user manual (class codes below).
"""

from __future__ import annotations

import math
import os

import numpy as np

from backend import config
from backend.data.grid import Grid

# vsicurl tuning: don't list the bucket, just range-read the one COG we ask for.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MULTIPLEX", "YES")

_S3_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"

# WorldCover class -> (fuel factor, flammable?). Factors are tuned for the CA:
# forest/shrub carry more fuel than grass; crops less; bare little.
_CLASS_TABLE: dict[int, tuple[float, bool]] = {
    10: (1.30, True),   # Tree cover
    20: (1.20, True),   # Shrubland
    30: (1.00, True),   # Grassland
    40: (0.70, True),   # Cropland
    50: (0.00, False),  # Built-up        -> non-flammable
    60: (0.35, True),   # Bare / sparse vegetation
    70: (0.00, False),  # Snow and ice    -> non-flammable
    80: (0.00, False),  # Permanent water -> non-flammable (natural firebreak)
    90: (0.45, True),   # Herbaceous wetland
    95: (0.60, True),   # Mangroves
    100: (0.50, True),  # Moss and lichen
}
_DEFAULT_FUEL = 0.8


def _tile_name(lon: float, lat: float) -> str:
    """WorldCover 3-degree tile name for a coordinate, e.g. 'N18E096'."""
    lat3 = int(math.floor(lat / 3.0) * 3)
    lon3 = int(math.floor(lon / 3.0) * 3)
    ns = "N" if lat3 >= 0 else "S"
    ew = "E" if lon3 >= 0 else "W"
    return f"{ns}{abs(lat3):02d}{ew}{abs(lon3):03d}"


def _read_classes(grid: Grid) -> np.ndarray:
    """Windowed, downsampled read of WorldCover onto the grid.

    WorldCover is tiled on a 3-degree grid; a bbox that spans more than one tile
    (e.g. a whole province) is mosaicked by reading each intersecting tile's
    window into the matching block of the output grid.
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    classes = np.zeros(grid.shape, dtype=np.int16)
    lat0, lat1, lon0, lon1 = grid.lat_min, grid.lat_max, grid.lon_min, grid.lon_max
    for lat3 in range(int(math.floor(lat0 / 3) * 3), int(math.floor(lat1 / 3) * 3) + 3, 3):
        for lon3 in range(int(math.floor(lon0 / 3) * 3), int(math.floor(lon1 / 3) * 3) + 3, 3):
            slon0, slon1 = max(lon0, lon3), min(lon1, lon3 + 3)
            slat0, slat1 = max(lat0, lat3), min(lat1, lat3 + 3)
            if slon1 <= slon0 or slat1 <= slat0:
                continue
            ns, ew = ("N" if lat3 >= 0 else "S"), ("E" if lon3 >= 0 else "W")
            tile = f"{ns}{abs(lat3):02d}{ew}{abs(lon3):03d}"
            url = f"{_S3_BASE}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            r_a, c_l = grid.lonlat_to_rowcol(slon0, slat1)  # NW of sub-extent
            r_b, c_r = grid.lonlat_to_rowcol(slon1, slat0)  # SE
            r0, r1 = min(r_a, r_b), max(r_a, r_b) + 1
            c0, c1 = min(c_l, c_r), max(c_l, c_r) + 1
            if r1 <= r0 or c1 <= c0:
                continue
            try:
                with rasterio.open(url) as ds:
                    win = from_bounds(slon0, slat0, slon1, slat1, transform=ds.transform)
                    data = ds.read(1, window=win, out_shape=(r1 - r0, c1 - c0),
                                   resampling=Resampling.nearest)
                    classes[r0:r1, c0:c1] = data.astype(np.int16)
            except Exception:  # tile missing (ocean) / transient network — leave as 0
                pass
    return classes


def get_fuel(grid: Grid, *, force_refresh: bool = False) -> dict:
    """Return {fuel_factor, nonflammable, landcover} on the master grid.

    Cached as ``.npy`` so offline demos and repeat requests are instant.
    """
    if config.DATA_MODE == "mock":
        from backend.data import mock

        return mock.mock_fuel(grid)

    cache = config.CACHE_DIR / f"landcover_{grid.n_rows}x{grid.n_cols}.npy"
    if cache.exists() and not force_refresh:
        classes = np.load(cache)
    else:
        classes = _read_classes(grid)
        np.save(cache, classes)

    return classes_to_fuel(classes)


def classes_to_fuel(classes: np.ndarray) -> dict:
    """Map a WorldCover class array to fuel factor + non-flammable mask."""
    fuel = np.full(classes.shape, _DEFAULT_FUEL, dtype=np.float64)
    nonflam = np.zeros(classes.shape, dtype=bool)
    for code, (factor, flammable) in _CLASS_TABLE.items():
        m = classes == code
        fuel[m] = factor
        if not flammable:
            nonflam[m] = True
    return {"fuel_factor": fuel, "nonflammable": nonflam, "landcover": classes}


if __name__ == "__main__":
    g = Grid.from_config()
    f = get_fuel(g)
    uniq, cnt = np.unique(f["landcover"], return_counts=True)
    print("land-cover class counts:", dict(zip(uniq.tolist(), cnt.tolist())))
    print(f"non-flammable cells: {f['nonflammable'].sum()} / {g.n_rows * g.n_cols}")
    print(f"fuel factor: {f['fuel_factor'].min():.2f}..{f['fuel_factor'].max():.2f}")
