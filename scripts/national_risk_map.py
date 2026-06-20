"""
national_risk_map.py - NATIONAL AI fire-susceptibility map for Thailand.

Trains the same GradientBoosting model but country-wide: labels = the whole
FIRMS archive CSV (fires across Thailand), features = elevation/slope/aspect +
WorldCover fuel + distance-to-built-up, on a coarse national grid (~5 km, no CA).

Saves (served by GET /api/national + used in the pitch):
  backend/cache/national_risk.npy
  backend/cache/national_meta.json
  scripts/out/national_risk.png

Usage:
  python scripts/national_risk_map.py --csv backend/cache/firms_dl/fire_archive_SV-C2_764878.csv
"""

import argparse
import csv
import json
import math
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np

from backend import config
from backend.data import terrain as terrain_mod
from backend.data.fuel import classes_to_fuel
from backend.data.grid import Grid
from backend.ml.features import feature_stack

_M = 111_320.0
OUT = pathlib.Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
WC_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"


def national_grid(bbox, cell_m):
    lon0, lat0, lon1, lat1 = bbox
    mid = math.radians((lat0 + lat1) / 2)
    nc = max(1, round((lon1 - lon0) * _M * math.cos(mid) / cell_m))
    nr = max(1, round((lat1 - lat0) * _M / cell_m))
    return Grid(lon0, lat0, lon1, lat1, nr, nc)


def load_fires(path, bbox):
    lon0, lat0, lon1, lat1 = bbox
    pts = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except (KeyError, ValueError):
                continue
            if lon0 <= lon <= lon1 and lat0 <= lat <= lat1:
                pts.append((lat, lon))
    return pts


def national_landcover(grid):
    """Mosaic WorldCover across the 3-degree tiles intersecting the national grid."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

    cache = config.CACHE_DIR / f"national_landcover_{grid.n_rows}x{grid.n_cols}.npy"
    if cache.exists():
        print(f"  landcover from cache {cache.name}")
        return np.load(cache)

    classes = np.zeros(grid.shape, dtype=np.int16)
    lat0, lat1, lon0, lon1 = grid.lat_min, grid.lat_max, grid.lon_min, grid.lon_max
    for lat3 in range(int(math.floor(lat0 / 3) * 3), int(math.floor(lat1 / 3) * 3) + 3, 3):
        for lon3 in range(int(math.floor(lon0 / 3) * 3), int(math.floor(lon1 / 3) * 3) + 3, 3):
            slon0, slon1 = max(lon0, lon3), min(lon1, lon3 + 3)
            slat0, slat1 = max(lat0, lat3), min(lat1, lat3 + 3)
            if slon1 <= slon0 or slat1 <= slat0:
                continue
            tile = f"N{lat3:02d}E{lon3:03d}"
            url = f"{WC_BASE}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            r_a, c_l = grid.lonlat_to_rowcol(slon0, slat1)  # north-west of sub-extent
            r_b, c_r = grid.lonlat_to_rowcol(slon1, slat0)  # south-east
            r0, r1 = min(r_a, r_b), max(r_a, r_b) + 1
            c0, c1 = min(c_l, c_r), max(c_l, c_r) + 1
            h, w = r1 - r0, c1 - c0
            if h <= 0 or w <= 0:
                continue
            try:
                with rasterio.open(url) as ds:
                    win = from_bounds(slon0, slat0, slon1, slat1, transform=ds.transform)
                    data = ds.read(1, window=win, out_shape=(h, w), resampling=Resampling.nearest)
                    classes[r0:r1, c0:c1] = data.astype(np.int16)
                    print(f"  {tile}: filled {h}x{w}")
            except Exception as exc:
                print(f"  {tile}: skip ({type(exc).__name__})")
    np.save(cache, classes)
    return classes


def thailand_mask(grid):
    """Boolean grid mask: True for cells inside Thailand's real border.

    Fetches a low-res Thailand boundary GeoJSON (cached) and rasterises it onto
    the grid so the overlay is clipped to the country, not the bounding box.
    """
    import requests
    from rasterio.features import rasterize
    from rasterio.transform import Affine

    cache = config.CACHE_DIR / "thailand.geojson"
    try:
        if cache.exists():
            gj = json.loads(cache.read_text())
        else:
            url = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/THA.geo.json"
            gj = requests.get(url, timeout=30).json()
            cache.write_text(json.dumps(gj))
        geoms = []
        for feat in gj.get("features", [gj]):
            g = feat.get("geometry", feat)
            if g:
                geoms.append((g, 1))
        mask = rasterize(geoms, out_shape=grid.shape, transform=Affine(*grid.affine()),
                         fill=0, dtype="uint8")
        return mask.astype(bool)
    except Exception as exc:
        print(f"      ! Thailand border mask failed ({exc}) — keeping full bbox")
        return np.ones(grid.shape, dtype=bool)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="backend/cache/firms_dl/fire_archive_SV-C2_764878.csv")
    ap.add_argument("--bbox", default="97.3,5.5,105.7,20.6", help="Thailand lon0,lat0,lon1,lat1")
    ap.add_argument("--cell-m", type=float, default=5000.0)
    ap.add_argument("--zoom", type=int, default=7)
    ap.add_argument("--neg-ratio", type=float, default=2.0)
    args = ap.parse_args()

    bbox = tuple(float(x) for x in args.bbox.split(","))
    grid = national_grid(bbox, args.cell_m)
    print(f"National grid {grid.n_rows}x{grid.n_cols} (~{args.cell_m/1000:.0f} km)  bbox {bbox}")

    print("[1/5] terrain (coarse DEM) ...")
    terrain = terrain_mod.get_terrain(grid, zoom=args.zoom)
    print("[2/5] land cover (WorldCover mosaic) ...")
    classes = national_landcover(grid)
    fuel = classes_to_fuel(classes)
    nodata = classes == 0
    fuel["nonflammable"] = fuel["nonflammable"] | nodata  # ocean / missing -> not land

    print("[3/5] features + labels ...")
    stack, names = feature_stack(grid, terrain, fuel)
    flammable = ~fuel["nonflammable"]
    fires = load_fires(args.csv, bbox)
    print(f"      fires in bbox: {len(fires)}")
    pos = np.zeros(grid.shape, dtype=bool)
    for lat, lon in fires:
        if grid.contains(lon, lat):
            r, c = grid.lonlat_to_rowcol(lon, lat)
            pos[r, c] = True
    pos &= flammable
    n_pos = int(pos.sum())
    neg_pool = np.argwhere(flammable & ~pos)
    rng = np.random.default_rng(0)
    n_neg = min(len(neg_pool), int(args.neg_ratio * n_pos))
    neg_idx = neg_pool[rng.choice(len(neg_pool), size=n_neg, replace=False)]
    pos_idx = np.argwhere(pos)
    print(f"      positive cells={n_pos}  negatives={n_neg}")

    X = np.vstack([stack[r, c] for r, c in pos_idx] + [stack[r, c] for r, c in neg_idx])
    y = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])

    print("[4/5] training national model ...")
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    model = GradientBoostingClassifier(random_state=0)
    model.fit(Xtr, ytr)
    auc = float(roc_auc_score(yte, model.predict_proba(Xte)[:, 1]))
    importances = {n: round(float(i), 3) for n, i in zip(names, model.feature_importances_)}
    print(f"      national ROC-AUC: {auc:.3f}  importances={importances}")

    print("[5/5] predicting national grid + saving ...")
    h, w, f = stack.shape
    risk = model.predict_proba(stack.reshape(-1, f))[:, 1].reshape(h, w)
    risk = np.clip(risk, 0, 1)
    risk[fuel["nonflammable"]] = 0.0
    inth = thailand_mask(grid)
    risk[~inth] = 0.0
    print(f"      clipped to Thailand border: {int(inth.sum())} cells inside")

    np.save(config.CACHE_DIR / "national_risk.npy", risk.astype(np.float32))
    meta = {
        "bounds": grid.leaflet_bounds(),
        "auc": round(auc, 3), "n_pos": n_pos, "n_neg": n_neg,
        "cell_km": args.cell_m / 1000, "importances": importances,
        "n_fires": len(fires),
    }
    (config.CACHE_DIR / "national_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"      saved national_risk.npy + national_meta.json")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ext = [grid.lon_min, grid.lon_max, grid.lat_min, grid.lat_max]
        fig, ax = plt.subplots(figsize=(7, 10))
        ax.imshow(np.ma.masked_where(risk <= 0.01, risk), cmap="YlOrRd", vmin=0, vmax=1,
                  extent=ext, origin="upper")
        flat = fires[:: max(1, len(fires) // 4000)]
        ax.scatter([lo for _, lo in flat], [la for la, _ in flat], s=0.5, c="#1769aa", alpha=0.25)
        ax.set_title(f"Thailand AI fire-susceptibility (AUC {auc:.2f}, {len(fires)} fires)")
        ax.set_xlabel("lon"); ax.set_ylabel("lat")
        fig.tight_layout()
        fig.savefig(OUT / "national_risk.png", dpi=110, bbox_inches="tight")
        print(f"      wrote {OUT/'national_risk.png'}")
    except Exception as exc:
        print(f"      (figure skipped: {exc})")


if __name__ == "__main__":
    main()
