"""
prefetch.py - Fetch & cache all real data for the configured area.

Run this once BEFORE a demo (while you have network). It downloads and caches:
  * Open-Meteo weather       -> cache/weather.json
  * Terrarium DEM tiles      -> cache/terrain_tiles/*.png  + gridded .npy
  * ESA WorldCover land cover-> cache/landcover_*.npy
and renders a preview PNG (scripts/out/layers.png) so you can eyeball that
every layer lines up on the grid. After this, the app works offline.

Usage:
    python scripts/prefetch.py            # fetch + cache + preview
    python scripts/prefetch.py --no-plot  # fetch + cache only
"""

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np

from backend import config
from backend.data import fuel as fuel_mod
from backend.data import terrain as terrain_mod
from backend.data import weather as weather_mod
from backend.data.grid import Grid
from backend.models.risk_fwi import compute_risk

OUT = pathlib.Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


def main(plot: bool = True):
    grid = Grid.from_config()
    print(f"Area: {config.AREA_NAME}  ({config.DATA_MODE} mode)")
    print(f"Grid: {grid.n_rows} x {grid.n_cols}  (~{grid.cell_size_m:.0f} m cells)")
    print(f"BBox: {grid.leaflet_bounds()}\n")

    t0 = time.time()
    print("[1/4] weather (Open-Meteo) ...")
    wx = weather_mod.get_area_weather(grid, force_refresh=True)
    rep = wx["representative"]
    print(f"      source={wx['source']}  T={rep['temp']}C RH={rep['rh']}% "
          f"wind={rep['wind_speed']} m/s @ {rep['wind_dir']} deg  rain24h={rep['rain_24h']} mm")

    print("[2/4] terrain (Terrarium DEM) ...")
    ter = terrain_mod.get_terrain(grid, force_refresh=True)
    e = ter["elevation"]
    print(f"      elevation {e.min():.0f}..{e.max():.0f} m  slope max {ter['slope_deg'].max():.0f} deg")

    print("[3/4] land cover (ESA WorldCover) ...")
    fu = fuel_mod.get_fuel(grid, force_refresh=True)
    uniq, cnt = np.unique(fu["landcover"], return_counts=True)
    print(f"      classes={dict(zip(uniq.tolist(), cnt.tolist()))}  "
          f"non-flammable={fu['nonflammable'].sum()} cells")

    print("[4/4] risk (FWI) ...")
    risk = compute_risk(grid, weather=wx, terrain=ter, fuel=fu)
    print(f"      FFMC={risk['ffmc_scalar']}  ISI={risk['isi_scalar']}  "
          f"danger={risk['danger_class']}")
    print(f"\nDone in {time.time() - t0:.1f}s. Cache dir: {config.CACHE_DIR}")

    if not plot:
        return

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(2, 2, figsize=(12, 11))
    ext = [grid.lon_min, grid.lon_max, grid.lat_min, grid.lat_max]
    kw = dict(extent=ext, origin="upper")

    im0 = ax[0, 0].imshow(e, cmap="terrain", **kw)
    ax[0, 0].set_title("Elevation (m) - Terrarium DEM")
    fig.colorbar(im0, ax=ax[0, 0], fraction=0.046)

    im1 = ax[0, 1].imshow(ter["slope_deg"], cmap="magma", **kw)
    ax[0, 1].set_title("Slope (deg)")
    fig.colorbar(im1, ax=ax[0, 1], fraction=0.046)

    im2 = ax[1, 0].imshow(fu["landcover"], cmap="tab20", **kw)
    ax[1, 0].set_title("Land cover class - ESA WorldCover")
    fig.colorbar(im2, ax=ax[1, 0], fraction=0.046)

    im3 = ax[1, 1].imshow(risk["risk"], cmap="YlOrRd", vmin=0, vmax=1, **kw)
    ax[1, 1].set_title(f"Fire risk 0-1 (FWI)  danger={risk['danger_class']}")
    fig.colorbar(im3, ax=ax[1, 1], fraction=0.046)

    for a in ax.flat:
        for asset in config.ASSETS:
            a.plot(asset["lon"], asset["lat"], "k^", markersize=7)
        a.set_xlabel("lon"); a.set_ylabel("lat")
    fig.suptitle(f"{config.AREA_NAME} - data layers on the master grid", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT / "layers.png", dpi=100, bbox_inches="tight")
    print(f"wrote {OUT / 'layers.png'}")


if __name__ == "__main__":
    main(plot="--no-plot" not in sys.argv)
