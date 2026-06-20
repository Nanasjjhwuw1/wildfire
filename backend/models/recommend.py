"""
recommend.py - Turn a burn-probability map into actionable suppression advice.

From a finished Monte-Carlo simulation we derive, as georeferenced GeoJSON:

  * fire_head        - the cell where fire spreads fastest & furthest (the
                       point downwind of ignition with high burn prob and the
                       largest along-wind distance). Stop the head first.
  * suppression_zone - a few prioritised points on the *advancing frontier*
                       (partially-burnt cells, 0.15-0.75 prob) weighted toward
                       the head and toward assets worth protecting.
  * firebreak_suggested - a line to cut just beyond the head, perpendicular to
                       the spread direction.
  * firebreak_natural   - existing water bodies touching the fire that already
                       act as barriers (anchor your line to these).
  * asset             - each protected community, tagged with its threat level.

Everything is computed in grid space then converted to lon/lat via the Grid,
so the output drops straight onto the map in the right place.
"""

from __future__ import annotations

import math

import numpy as np

from backend.data.grid import Grid


def recommend(
    grid: Grid,
    burn_prob: np.ndarray,
    ignition_rc: tuple[int, int],
    wind_dir_deg: float,
    fuel: dict,
    assets: list[dict],
    *,
    max_zones: int = 5,
) -> dict:
    h, w = burn_prob.shape
    ri, ci = ignition_rc

    # Downwind direction as a grid-space unit vector (row grows south, col east).
    blow = math.radians((wind_dir_deg + 180.0) % 360.0)
    drow, dcol = -math.cos(blow), math.sin(blow)
    norm = math.hypot(drow, dcol) or 1.0
    drow, dcol = drow / norm, dcol / norm
    prow, pcol = -dcol, drow  # perpendicular (along the fire flank)

    rows, cols = np.indices((h, w))
    proj = (rows - ri) * drow + (cols - ci) * dcol  # along-wind distance (cells)

    # --- fire head: high-prob cell furthest downwind ----------------------
    burning = burn_prob > 0.3
    if burning.any():
        rh, ch = np.unravel_index(np.argmax(np.where(burning, proj, -1e9)), (h, w))
        proj_peak = max(float(proj[burning].max()), 1.0)
    else:
        rh, ch = ri, ci
        proj_peak = 1.0

    # --- assets: threat = max burn prob in a small disk -------------------
    asset_rc = [grid.lonlat_to_rowcol(a["lon"], a["lat"]) for a in assets]

    def disk_max(r, c, rad=3):
        r0, r1 = max(0, r - rad), min(h, r + rad + 1)
        c0, c1 = max(0, c - rad), min(w, c + rad + 1)
        return float(burn_prob[r0:r1, c0:c1].max())

    asset_threat = [disk_max(r, c) for r, c in asset_rc]

    dist_asset = np.full((h, w), 1e9)
    for r, c in asset_rc:
        dist_asset = np.minimum(dist_asset, np.hypot(rows - r, cols - c))

    # --- suppression candidates: advancing frontier, biased to head+assets
    frontier = (burn_prob > 0.15) & (burn_prob < 0.75)
    proj_norm = np.clip(proj / proj_peak, 0.0, 1.0)
    asset_bonus = np.exp(-dist_asset / 12.0)  # ~1 next to an asset, decaying out
    score = np.where(frontier, burn_prob * (0.5 + proj_norm) * (1.0 + asset_bonus), 0.0)

    # greedily pick well-separated high-score cells
    zones: list[tuple[int, int]] = []
    work = score.copy()
    for _ in range(max_zones):
        if work.max() <= 0:
            break
        zr, zc = np.unravel_index(np.argmax(work), (h, w))
        zones.append((int(zr), int(zc)))
        r0, r1 = max(0, zr - 8), min(h, zr + 9)
        c0, c1 = max(0, zc - 8), min(w, zc + 9)
        work[r0:r1, c0:c1] = 0.0

    # --- natural barriers: water cells touching the burn ------------------
    natural = []
    if "landcover" in fuel:
        burned = burn_prob > 0.2
        dil = burned.copy()
        dil[1:, :] |= burned[:-1, :]; dil[:-1, :] |= burned[1:, :]
        dil[:, 1:] |= burned[:, :-1]; dil[:, :-1] |= burned[:, 1:]
        water_barrier = (fuel["landcover"] == 80) & dil
        wr, wc = np.where(water_barrier)
        for r, c in list(zip(wr.tolist(), wc.tolist()))[:25]:
            natural.append(grid.rowcol_to_lonlat(r, c))

    # --- assemble GeoJSON -------------------------------------------------
    feats = []
    hlon, hlat = grid.rowcol_to_lonlat(rh, ch)
    feats.append(_pt(hlon, hlat, kind="fire_head", label="Fire head — stop forward spread here"))

    for i, (zr, zc) in enumerate(zones):
        lon, lat = grid.rowcol_to_lonlat(zr, zc)
        feats.append(_pt(lon, lat, kind="suppression_zone", priority=i + 1,
                         label=f"Suppression priority {i + 1}",
                         burn_prob=round(float(burn_prob[zr, zc]), 2)))

    # suggested firebreak: a line just beyond the head, across the flank
    off, halfw = 5.0, 12.0
    ar, ac = rh + drow * off, ch + dcol * off
    e1 = grid.rowcol_to_lonlat(int(round(ar + prow * halfw)), int(round(ac + pcol * halfw)))
    e2 = grid.rowcol_to_lonlat(int(round(ar - prow * halfw)), int(round(ac - pcol * halfw)))
    feats.append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [list(e1), list(e2)]},
        "properties": {"kind": "firebreak_suggested",
                       "label": "Suggested firebreak (cut perpendicular to the head)"},
    })

    if natural:
        feats.append({
            "type": "Feature",
            "geometry": {"type": "MultiPoint", "coordinates": [list(p) for p in natural]},
            "properties": {"kind": "firebreak_natural", "label": "Natural barrier (water) — anchor here"},
        })

    for a, (r, c), th in zip(assets, asset_rc, asset_threat):
        feats.append(_pt(a["lon"], a["lat"], kind="asset", label=a["name"], threat=round(th, 2)))

    return {
        "type": "FeatureCollection",
        "features": feats,
        "summary": {
            "fire_head": [round(hlon, 5), round(hlat, 5)],
            "n_suppression_zones": len(zones),
            "assets_threatened": int(sum(1 for t in asset_threat if t > 0.2)),
            "wind_dir_deg": wind_dir_deg,
        },
    }


def _pt(lon, lat, **props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props}
