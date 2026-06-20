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
    """Windowed, downsampled read of the WorldCover class raster onto the grid."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    tile = _tile_name((grid.lon_min + grid.lon_max) / 2, (grid.lat_min + grid.lat_max) / 2)
    url = f"{_S3_BASE}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"

    with rasterio.open(url) as ds:
        window = from_bounds(
            grid.lon_min, grid.lat_min, grid.lon_max, grid.lat_max, transform=ds.transform
        )
        classes = ds.read(
            1,
            window=window,
            out_shape=(grid.n_rows, grid.n_cols),
            resampling=Resampling.nearest,  # categorical -> nearest, never average
        )
    return classes.astype(np.int16)


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
