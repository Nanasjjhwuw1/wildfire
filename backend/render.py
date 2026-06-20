"""
render.py - Turn 2-D model arrays into georeferenced PNG overlays.

The frontend places these as Leaflet ``ImageOverlay``s using the grid bounds.
Row 0 of every array is the NORTH edge (top of the PNG), which is how Leaflet
positions an image against ``[[south, west], [north, east]]`` - no flip needed.

Output is a base64 ``data:`` URL so the API response is self-contained.

Colour maps are tiny hand-coded lookup tables (no matplotlib import) so the
server stays lightweight enough for small free-tier instances.
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

# A few colour-stop lookup tables (RGB 0-255), interpolated linearly.
_CMAPS = {
    "YlOrRd": [(255, 255, 178), (254, 204, 92), (253, 141, 60), (240, 59, 32), (189, 0, 38)],
    "inferno": [(0, 0, 4), (87, 16, 110), (188, 55, 84), (249, 142, 9), (252, 255, 164)],
    "cool": [(0, 255, 255), (64, 128, 255), (160, 64, 255), (255, 0, 255)],
}


def _colormap(v: np.ndarray, name: str) -> np.ndarray:
    """Map values in [0,1] to (H, W, 3) float RGB via a small LUT."""
    stops = np.asarray(_CMAPS.get(name, _CMAPS["YlOrRd"]), dtype=float)
    n = len(stops)
    x = np.clip(v, 0.0, 1.0) * (n - 1)
    i0 = np.clip(np.floor(x).astype(int), 0, n - 2)
    f = (x - i0)[..., None]
    return stops[i0] * (1.0 - f) + stops[i0 + 1] * f


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
    rgba = np.zeros((*v.shape, 4), dtype=np.uint8)
    rgba[..., :3] = _colormap(v, cmap).astype(np.uint8)
    transparent = v < hide_below
    if mask is not None:
        transparent = transparent | np.asarray(mask, dtype=bool)
    rgba[..., 3] = np.where(transparent, 0, 220).astype(np.uint8)
    return rgba


def to_data_url(rgba: np.ndarray) -> str:
    """Encode an RGBA array as a PNG data URL."""
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def overlay_png(values, cmap="YlOrRd", mask=None, hide_below=0.02) -> str:
    """Convenience: colorize + encode in one call."""
    return to_data_url(colorize(values, cmap=cmap, mask=mask, hide_below=hide_below))
