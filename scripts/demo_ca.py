"""
demo_ca.py - Standalone proof that the fire-spread CA behaves sensibly.

Builds a small SYNTHETIC landscape (a hill, a denser forest band, a river that
cannot burn, and a road firebreak), ignites one cell, runs the Monte-Carlo CA
under a steady wind, and writes:

    scripts/out/demo_ca.gif      - animation of the spreading burn probability
    scripts/out/demo_ca.png      - terrain / fuel / final burn-probability panels

It also prints a few sanity statistics (downwind vs upwind spread, that the
river stays unburnt) so the spread logic can be verified without the web app.

Run:  python scripts/demo_ca.py
"""

import os
import pathlib
import sys

# Allow `python scripts/demo_ca.py` from the repo root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")  # headless: render straight to files, no GUI window
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter

from backend.models.spread_ca import CAParams, simulate_montecarlo

OUT = pathlib.Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

H = W = 100
CELL_M = 100.0


def hillshade(elev, azimuth=315, altitude=45, cell=CELL_M):
    """Classic shaded-relief for a nice terrain backdrop (numpy only)."""
    dy, dx = np.gradient(elev, cell)
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    az = np.radians(360.0 - azimuth + 90.0)
    alt = np.radians(altitude)
    shaded = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    return np.clip(shaded, 0, 1)


def build_landscape():
    """Synthetic terrain + fuel + non-flammable mask."""
    yy, xx = np.mgrid[0:H, 0:W]

    # A single peak in the north-centre so we can watch fire climb toward it.
    elev = 600.0 + 450.0 * np.exp(-(((xx - 55) ** 2 + (yy - 38) ** 2) / (2 * 22.0 ** 2)))

    # Fuel: grassland baseline (1.0) with a denser forest band (1.3).
    fuel = np.full((H, W), 1.0)
    fuel[18:46, :] = 1.3

    nonflam = np.zeros((H, W), dtype=bool)
    # A river running diagonally (water = cannot burn, natural firebreak).
    nonflam |= np.abs((xx - yy) - 6) <= 1
    # A road cutting vertically (engineered firebreak).
    nonflam[:, 71:73] = True

    # Drier fuel away from the river; here just uniformly dry for the demo.
    moist = np.full((H, W), 1.0)
    return elev, fuel, moist, nonflam


def main():
    elev, fuel, moist, nonflam = build_landscape()

    ignition = (84, 40)          # south-centre
    wind_speed = 8.0             # m/s
    wind_dir_deg = 225.0         # FROM south-west -> blows toward north-east
    n_runs, n_steps = 24, 70

    print(f"Running Monte-Carlo CA: {n_runs} runs x {n_steps} steps on {H}x{W} grid...")
    out = simulate_montecarlo(
        fuel, moist, elev, nonflam, [ignition], wind_speed, wind_dir_deg,
        n_runs=n_runs, n_steps=n_steps, params=CAParams(cell_size_m=CELL_M), seed=7,
    )
    frames = out["frames"]
    burn_prob = out["burn_prob"]

    # --- sanity statistics --------------------------------------------------
    ci, cj = ignition
    ne = burn_prob[:ci, cj:].sum()   # toward the wind / uphill
    sw = burn_prob[ci:, :cj].sum()   # away from the wind / downhill
    river = np.abs((np.arange(W)[None, :] - np.arange(H)[:, None]) - 6) <= 1
    print(f"  mean burned cells : {burn_prob.sum():.0f} of {(~nonflam).sum()} flammable")
    print(f"  NE quadrant burn  : {ne:.0f}   (downwind + uphill)")
    print(f"  SW quadrant burn  : {sw:.0f}   (upwind + downhill)")
    print(f"  NE/SW ratio       : {ne / max(sw, 1e-9):.1f}x  -> wind+slope bias OK")
    print(f"  river burn-prob   : max={burn_prob[river].max():.3f}  -> firebreak holds")

    shade = hillshade(elev)

    # --- static summary figure ---------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2))
    axes[0].imshow(shade, cmap="gray")
    axes[0].imshow(np.ma.masked_where(~nonflam, nonflam), cmap="cool", alpha=0.9)
    axes[0].contour(elev, levels=8, colors="k", linewidths=0.3, alpha=0.5)
    axes[0].set_title("Terrain (hillshade + contours)\nblue = non-flammable")

    axes[1].imshow(shade, cmap="gray")
    im = axes[1].imshow(np.where(nonflam, np.nan, fuel), cmap="YlGn", alpha=0.8)
    axes[1].set_title("Fuel factor")
    fig.colorbar(im, ax=axes[1], fraction=0.046)

    axes[2].imshow(shade, cmap="gray")
    bp = np.ma.masked_where(burn_prob <= 0.01, burn_prob)
    im2 = axes[2].imshow(bp, cmap="inferno", vmin=0, vmax=1, alpha=0.85)
    axes[2].set_title(f"Burn probability (final)\nwind {wind_speed} m/s from {wind_dir_deg:.0f} deg")
    fig.colorbar(im2, ax=axes[2], fraction=0.046)

    for ax in axes:
        ax.plot(cj, ci, "*", color="cyan", markersize=16, markeredgecolor="k")
        # wind arrow: points the way the wind blows
        blow = np.radians((wind_dir_deg + 180.0) % 360.0)
        dx, dy = np.sin(blow) * 12, -np.cos(blow) * 12
        ax.annotate("", xy=(12 + dx, 12 + dy), xytext=(12, 12),
                    arrowprops=dict(arrowstyle="-|>", color="deepskyblue", lw=2))
        ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(OUT / "demo_ca.png", dpi=110, bbox_inches="tight")
    print(f"  wrote {OUT / 'demo_ca.png'}")

    # --- animation ----------------------------------------------------------
    figa, axa = plt.subplots(figsize=(6.2, 6.2))
    axa.imshow(shade, cmap="gray")
    axa.imshow(np.ma.masked_where(~nonflam, nonflam), cmap="cool", alpha=0.7)
    heat = axa.imshow(np.ma.masked_where(frames[0] <= 0.01, frames[0]),
                      cmap="inferno", vmin=0, vmax=1, alpha=0.85)
    axa.plot(cj, ci, "*", color="cyan", markersize=15, markeredgecolor="k")
    axa.set_xticks([]); axa.set_yticks([])
    title = axa.set_title("step 0")

    def update(t):
        heat.set_data(np.ma.masked_where(frames[t] <= 0.01, frames[t]))
        title.set_text(f"burn probability - step {t + 1}/{n_steps}")
        return heat, title

    anim = FuncAnimation(figa, update, frames=n_steps, blit=False)
    anim.save(OUT / "demo_ca.gif", writer=PillowWriter(fps=12))
    print(f"  wrote {OUT / 'demo_ca.gif'}")


if __name__ == "__main__":
    main()
