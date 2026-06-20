"""
grid.py - The master georeferenced grid.

This is the backbone of "overlays land on the right place in the real world".
Every data layer (weather -> risk, DEM -> slope, land cover -> fuel) is
resampled onto ONE grid defined here, and every result the API returns carries
the same bounds so the frontend can place it with a Leaflet ImageOverlay.

Conventions (must match spread_ca.py):
  * row 0 is the NORTH edge; increasing row index goes SOUTH (lat decreases).
  * col 0 is the WEST edge;  increasing col index goes EAST  (lon increases).
  * cell (row, col) refers to a cell *centre* when we need a single coordinate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from backend import config

_M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class Grid:
    lon_min: float
    lat_min: float
    lon_max: float
    lat_max: float
    n_rows: int
    n_cols: int

    # --- constructors ------------------------------------------------------
    @classmethod
    def from_config(cls) -> "Grid":
        lon0, lat0, lon1, lat1 = config.BBOX
        return cls(lon0, lat0, lon1, lat1, config.GRID_ROWS, config.GRID_COLS)

    # --- per-cell sizes ----------------------------------------------------
    @property
    def dlon(self) -> float:
        return (self.lon_max - self.lon_min) / self.n_cols

    @property
    def dlat(self) -> float:
        return (self.lat_max - self.lat_min) / self.n_rows

    @property
    def mid_lat(self) -> float:
        return (self.lat_min + self.lat_max) / 2.0

    @property
    def cell_width_m(self) -> float:
        """East-west size of a cell in metres (varies with latitude)."""
        return self.dlon * _M_PER_DEG_LAT * math.cos(math.radians(self.mid_lat))

    @property
    def cell_height_m(self) -> float:
        """North-south size of a cell in metres."""
        return self.dlat * _M_PER_DEG_LAT

    @property
    def cell_size_m(self) -> float:
        """Single representative cell size for the CA (cells are ~square here)."""
        return (self.cell_width_m + self.cell_height_m) / 2.0

    @property
    def shape(self) -> tuple[int, int]:
        return (self.n_rows, self.n_cols)

    # --- coordinate arrays (cell centres) ----------------------------------
    def cell_lats(self) -> np.ndarray:
        """1-D array of latitudes for each row centre (north -> south)."""
        return self.lat_max - (np.arange(self.n_rows) + 0.5) * self.dlat

    def cell_lons(self) -> np.ndarray:
        """1-D array of longitudes for each column centre (west -> east)."""
        return self.lon_min + (np.arange(self.n_cols) + 0.5) * self.dlon

    def meshgrid(self) -> tuple[np.ndarray, np.ndarray]:
        """(lon2d, lat2d) of cell centres, each shaped (n_rows, n_cols)."""
        return np.meshgrid(self.cell_lons(), self.cell_lats())

    # --- conversions -------------------------------------------------------
    def contains(self, lon: float, lat: float) -> bool:
        return (self.lon_min <= lon <= self.lon_max) and (self.lat_min <= lat <= self.lat_max)

    def lonlat_to_rowcol(self, lon: float, lat: float) -> tuple[int, int]:
        """Map a real-world coordinate to integer (row, col), clipped to grid."""
        col = int((lon - self.lon_min) / self.dlon)
        row = int((self.lat_max - lat) / self.dlat)  # north is row 0
        row = min(max(row, 0), self.n_rows - 1)
        col = min(max(col, 0), self.n_cols - 1)
        return row, col

    def rowcol_to_lonlat(self, row: int, col: int) -> tuple[float, float]:
        """Return the (lon, lat) of the centre of cell (row, col)."""
        lon = self.lon_min + (col + 0.5) * self.dlon
        lat = self.lat_max - (row + 0.5) * self.dlat
        return lon, lat

    # --- interop -----------------------------------------------------------
    def leaflet_bounds(self) -> list[list[float]]:
        """Bounds for L.imageOverlay / L.latLngBounds: [[south, west], [north, east]]."""
        return [[self.lat_min, self.lon_min], [self.lat_max, self.lon_max]]

    def affine(self) -> tuple[float, float, float, float, float, float]:
        """GDAL/rasterio affine coefficients (a, b, c, d, e, f) for this grid:
        lon = a*col + b*row + c ; lat = d*col + e*row + f, mapping pixel CORNER
        (col, row) -> upper-left geographic coordinate. Build with
        ``rasterio.transform.Affine(*grid.affine())``.
        """
        return (self.dlon, 0.0, self.lon_min, 0.0, -self.dlat, self.lat_max)

    def as_dict(self) -> dict:
        return {
            "bbox": [self.lon_min, self.lat_min, self.lon_max, self.lat_max],
            "bounds": self.leaflet_bounds(),
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
            "cell_size_m": round(self.cell_size_m, 2),
        }


if __name__ == "__main__":
    g = Grid.from_config()
    print(f"{config.AREA_NAME}: {g.n_rows} rows x {g.n_cols} cols")
    print(f"cell ~= {g.cell_width_m:.1f} m (E-W) x {g.cell_height_m:.1f} m (N-S)")
    print(f"leaflet bounds: {g.leaflet_bounds()}")
    # Round-trip sanity: a known coordinate -> cell -> centre should stay close.
    lon, lat = 98.9217, 18.8048  # Wat Phra That Doi Suthep
    r, c = g.lonlat_to_rowcol(lon, lat)
    blon, blat = g.rowcol_to_lonlat(r, c)
    print(f"({lon}, {lat}) -> cell (row={r}, col={c}) -> centre ({blon:.4f}, {blat:.4f})")
    assert g.contains(lon, lat)
    assert abs(blon - lon) <= g.dlon and abs(blat - lat) <= g.dlat
    print("round-trip OK")
