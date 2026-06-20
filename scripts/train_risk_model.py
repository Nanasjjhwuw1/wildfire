"""
train_risk_model.py - Train the ML fire-susceptibility model on real FIRMS fires.

Pipeline (all real data):
  1. Download historical fire detections (NASA FIRMS) for a wide region over a
     past dry season  -> POSITIVE cells (a fire occurred there).
  2. Sample other flammable cells               -> NEGATIVE cells.
  3. Build static features (terrain + fuel + distance-to-built-up) for the region.
  4. Train a scikit-learn GradientBoosting classifier, report ROC-AUC on a
     held-out split + feature importances (ML, but explainable).
  5. Save the model to cache/risk_model.joblib for /api/risk_ml.

Usage (after putting FIRMS_API_KEY in .env):
    python scripts/train_risk_model.py
    python scripts/train_risk_model.py --start 2025-01-01 --end 2025-04-15 --sensor VIIRS_SNPP_SP
"""

import argparse
import csv
import io
import math
import pathlib
import sys
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import requests

from backend import config
from backend.data import fuel as fuel_mod
from backend.data import terrain as terrain_mod
from backend.data.grid import Grid
from backend.ml.features import feature_stack

_M_PER_DEG_LAT = 111_320.0
FIRMS_CSV = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/{area}/{days}/{start}"


def region_grid(bbox, cell_m) -> Grid:
    lon0, lat0, lon1, lat1 = bbox
    mid = math.radians((lat0 + lat1) / 2)
    n_cols = max(1, round((lon1 - lon0) * _M_PER_DEG_LAT * math.cos(mid) / cell_m))
    n_rows = max(1, round((lat1 - lat0) * _M_PER_DEG_LAT / cell_m))
    return Grid(lon0, lat0, lon1, lat1, n_rows, n_cols)


def fetch_firms_history(bbox, start, end, sensor, key) -> list[tuple[float, float]]:
    """Loop 10-day windows over [start, end]; return [(lat, lon), ...] in bbox.

    FIRMS throttles a key after a burst (returns HTTP 400 with empty body), so we
    retry each window with backoff and space requests out.
    """
    lon0, lat0, lon1, lat1 = bbox
    area = f"{lon0},{lat0},{lon1},{lat1}"
    pts, cur = [], start
    while cur <= end:
        span = min(10, (end - cur).days + 1)
        url = FIRMS_CSV.format(key=key, sensor=sensor, area=area, days=span, start=cur.isoformat())
        for attempt in range(15):
            try:
                resp = requests.get(url, timeout=60)
                if resp.status_code == 400:  # almost always the key's rate-limit here
                    print(f"  {cur}: HTTP 400 (rate-limit), wait 60s [{attempt + 1}/15]")
                    time.sleep(60)
                    continue
                resp.raise_for_status()
                text = resp.text
                if text.lstrip().lower().startswith(("invalid", "<!doctype", "<html")):
                    print(f"  ! {cur}: error page (check key/sensor)")
                    break
                rows = list(csv.DictReader(io.StringIO(text)))
                for r in rows:
                    try:
                        pts.append((float(r["latitude"]), float(r["longitude"])))
                    except (KeyError, ValueError):
                        pass
                print(f"  {cur} +{span}d : {len(rows)} detections")
                break
            except Exception as exc:
                print(f"  {cur}: {exc} — wait 60s [{attempt + 1}/15]")
                time.sleep(60)
        cur += timedelta(days=span)
        time.sleep(3)  # space windows out
    return pts


def load_fires_csv(path, bbox) -> list[tuple[float, float]]:
    """Load (lat, lon) from a FIRMS archive CSV, filtered to bbox (no rate limit)."""
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


def main():
    ap = argparse.ArgumentParser()
    # 2025 peak burning week (2026 SP not fully processed yet). One wide window =
    # few API calls (key throttles hard) but many fires.
    ap.add_argument("--start", default="2025-03-08")
    ap.add_argument("--end", default="2025-03-17")
    ap.add_argument("--sensor", default="VIIRS_SNPP_SP")
    ap.add_argument("--bbox", default="98.0,18.3,99.0,20.0",
                    help="lon0,lat0,lon1,lat1 (wide, within WorldCover tile N18E096)")
    ap.add_argument("--cell-m", type=float, default=700.0)
    ap.add_argument("--zoom", type=int, default=10)
    ap.add_argument("--neg-ratio", type=float, default=2.0)
    ap.add_argument("--csv", default=None,
                    help="path to a FIRMS archive CSV (download from the portal; skips the throttled API)")
    args = ap.parse_args()

    if not config.FIRMS_API_KEY and not args.csv:
        print("ERROR: need fire labels. Either:\n"
              "  (a) set FIRMS_API_KEY (free: https://firms.modaps.eosdis.nasa.gov/api/map_key/), or\n"
              "  (b) download a FIRMS archive CSV and pass --csv <path>\n"
              "      (portal: https://firms.modaps.eosdis.nasa.gov/download/ — no rate limit).")
        sys.exit(1)

    bbox = tuple(float(x) for x in args.bbox.split(","))
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    grid = region_grid(bbox, args.cell_m)
    print(f"Region {bbox}  grid {grid.n_rows}x{grid.n_cols} (~{args.cell_m:.0f} m)")
    print(f"FIRMS {args.sensor}  {start}..{end}")

    if args.csv:
        print(f"[1/4] loading fires from {args.csv} ...")
        fires = load_fires_csv(args.csv, bbox)
    else:
        print("[1/4] downloading FIRMS history ...")
        fires = fetch_firms_history(bbox, start, end, args.sensor, config.FIRMS_API_KEY)
    print(f"      total fire detections in region: {len(fires)}")
    if len(fires) < 30:
        print("      ! too few fires — try a wider bbox / different dry-season dates / sensor.")
        if not fires:
            sys.exit(2)

    print("[2/4] building region terrain + fuel ...")
    terrain = terrain_mod.get_terrain(grid, zoom=args.zoom)
    fuel = fuel_mod.get_fuel(grid)
    stack, names = feature_stack(grid, terrain, fuel)
    flammable = ~fuel["nonflammable"]

    print("[3/4] assembling training set ...")
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
    print(f"      positives={n_pos}  negatives={n_neg}")

    X = np.vstack([stack[r, c] for r, c in pos_idx] + [stack[r, c] for r, c in neg_idx])
    y = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])

    print("[4/4] training GradientBoosting ...")
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    model = GradientBoostingClassifier(random_state=0)
    model.fit(Xtr, ytr)
    auc = float(roc_auc_score(yte, model.predict_proba(Xte)[:, 1]))
    importances = {n: round(float(i), 3) for n, i in zip(names, model.feature_importances_)}
    print(f"      ROC-AUC (held-out): {auc:.3f}")
    print(f"      feature importance: {importances}")

    import joblib

    bundle = {
        "model": model,
        "feature_names": names,
        "metrics": {
            "auc": round(auc, 3), "n_pos": n_pos, "n_neg": n_neg,
            "region": bbox, "start": str(start), "end": str(end), "sensor": args.sensor,
            "importances": importances, "trained_at": date.today().isoformat(),
        },
    }
    out = config.CACHE_DIR / "risk_model.joblib"
    joblib.dump(bundle, out)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
