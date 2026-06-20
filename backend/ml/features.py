"""
features.py - Build the feature stack for the ML fire-susceptibility model.

We model *where fires tend to start* from static landscape predictors (the FWI
model already covers *when the weather is dangerous*, and the CA covers *how it
spreads* - this layer is complementary). Using the same builder for training and
inference guarantees identical feature order.

Predictors per grid cell:
  elevation        - metres (fires cluster at certain elevations)
  slope_deg        - steeper terrain
  aspect_sin/cos   - slope facing, encoded circularly (sun exposure)
  fuel_factor      - vegetation flammability from land cover
  dist_builtup_km  - distance to built-up land (human-ignition proximity)
"""

from __future__ import annotations

import numpy as np

FEATURE_NAMES = [
    "elevation", "slope_deg", "aspect_sin", "aspect_cos", "fuel_factor", "dist_builtup_km",
]


def feature_stack(grid, terrain: dict, fuel: dict) -> tuple[np.ndarray, list[str]]:
    """Return ((H, W, F) float array, feature_names) for a grid."""
    arad = np.radians(terrain["aspect_deg"])
    stack = np.stack(
        [
            terrain["elevation"].astype(float),
            terrain["slope_deg"].astype(float),
            np.sin(arad),
            np.cos(arad),
            fuel["fuel_factor"].astype(float),
            _dist_to_builtup_km(fuel.get("landcover"), grid),
        ],
        axis=-1,
    )
    return stack, list(FEATURE_NAMES)


def _dist_to_builtup_km(landcover, grid) -> np.ndarray:
    """Distance (km) from each cell to the nearest built-up cell (WorldCover 50)."""
    h, w = grid.shape
    if landcover is None:
        return np.full((h, w), 5.0)
    builtup = np.asarray(landcover) == 50
    if not builtup.any():
        return np.full((h, w), 10.0)  # nothing built-up in view -> treat as far
    from scipy.ndimage import distance_transform_edt

    d_cells = distance_transform_edt(~builtup)
    return d_cells * (grid.cell_size_m / 1000.0)
