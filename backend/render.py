"""
render.py - Turn 2-D model arrays into georeferenced PNG overlays.

The frontend places these as Leaflet ``ImageOverlay``s using the grid bounds.
Row 0 of every array is the NORTH edge (top of the PNG), which is exactly how
Leaflet positions an image against ``[[south, west], [north, east]]`` - so no
vertical flip is needed.

Output is a base64 ``data:`` URL so the API response is self-contained (no
extra static-file plumbing); the images are tiny (~111x105 px).
"""

from __future__ import annotations

import base64
import io

import numpy as np
from matplotlib import colormaps
from PIL import Image


def colorize(
    values: np.ndarray,
    cmap: str = "YlOrRd",
    vmin: float = 0.0,
    vmax: float = 1.0,
    mask: np.ndarray | None = None,
    hide_below: float = 0.02,
) -> np.ndarray:
    """Map a 2-D array to an (H, W, 4) RGBA uint8 image.

    Cells below ``hide_below`` (after scaling) or in ``mask`` become fully
    transparent so the basemap shows through where there's nothing to display.
    """
    v = np.clip((np.asarray(values, dtype=float) - vmin) / (vmax - vmin + 1e-12), 0.0, 1.0)
    rgba = (colormaps[cmap](v) * 255).astype(np.uint8)
    transparent = v < hide_below
    if mask is not None:
        transparent = transparent | np.asarray(mask, dtype=bool)
    rgba[..., 3] = np.where(transparent, 0, 220).astype(np.uint8)  # 220 = slight see-through
    return rgba


def to_data_url(rgba: np.ndarray) -> str:
    """Encode an RGBA array as a PNG data URL."""
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def overlay_png(values, cmap="YlOrRd", mask=None, hide_below=0.02) -> str:
    """Convenience: colorize + encode in one call."""
    return to_data_url(colorize(values, cmap=cmap, mask=mask, hide_below=hide_below))
