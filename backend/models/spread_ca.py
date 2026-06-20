"""
spread_ca.py - Wildfire spread via a Cellular Automaton (CA).

Model after:
  Alexandridis, A., Vakalis, D., Siettos, C.I., Bafas, G.V. (2008).
  "A cellular automata model for forest fire spread prediction: The case of
   the wildfire that swept through Spetses Island in 1990."
  Applied Mathematics and Computation 204(1), 191-201.

Each cell of a regular grid is in one of four states:

    UNBURNED      - has fuel, not yet ignited
    BURNING       - currently on fire; spreads to its 8 neighbours
    BURNED        - fuel consumed, now inert
    NONFLAMMABLE  - cannot burn (water, built-up area, bare rock, ...)

Spread rule (applied every timestep):
For each BURNING cell `s`, the probability that it ignites an adjacent
UNBURNED cell `t` is

    P(s -> t) = p0 * p_fuel * p_moist * p_wind(theta) * p_slope(phi)   (clipped to 0..1)

  p0       base propagation probability on flat ground with no wind
           (Alexandridis fit this to ~0.58 on Spetses Island).
  p_fuel   fuel factor. In the paper this is (1 + p_veg)(1 + p_den) combining
           vegetation *type* and *density*; here we accept a single
           pre-multiplied fuel factor per cell (>1 = burns easier).
  p_moist  MVP extension (not in the original paper): a dead-fuel-moisture
           damping factor in (0, 1] derived from live weather (humidity /
           rain). 1.0 = bone dry, smaller = wetter / harder to ignite.
  p_wind   = exp(c1 * V) * exp(c2 * V * (cos(theta) - 1))
           V    = wind speed [m/s]
           theta= angle between the direction the wind BLOWS towards and the
                  direction the fire is spreading (s -> t).
           Downwind (theta = 0)  -> cos = 1  -> maximum boost exp(c1*V).
           Upwind   (theta = 180)-> cos = -1 -> strongly suppressed.
           Constants from the paper: c1 = 0.045, c2 = 0.131.
  p_slope  = exp(a * phi)
           phi = terrain slope angle [degrees] from cell s up to cell t.
           Uphill (t higher than s) -> phi > 0 -> fire spreads faster
           (heat rises, pre-heats the upslope fuel). Constant a = 0.078.

If a cell has several burning neighbours the independent per-neighbour
probabilities combine as:  P_ignite(t) = 1 - product_s (1 - P(s -> t)).

The engine is fully vectorised over the grid (one array op per neighbour
direction per timestep), and `simulate_montecarlo` repeats the stochastic run
N times to produce a smooth *burn-probability* map plus per-timestep frames
for animation.

Geographic convention used throughout:
  - grid row index `i` increases SOUTHWARD (row 0 = north edge),
  - grid col index `j` increases EASTWARD  (col 0 = west edge),
  - wind direction is METEOROLOGICAL: degrees the wind blows *from*
    (0 = from north, 90 = from east, 180 = from south, 270 = from west).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

# --- cell states -----------------------------------------------------------
UNBURNED: int = 0
BURNING: int = 1
BURNED: int = 2
NONFLAMMABLE: int = 3

# 8-connected (Moore) neighbourhood offsets (di, dj).
_DIRS: tuple[tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)


@dataclass
class CAParams:
    """Tunable coefficients of the CA spread model (defaults = Alexandridis 2008)."""

    p0: float = 0.58          # base spread probability (flat, no wind)
    c1: float = 0.045         # wind-speed coefficient
    c2: float = 0.131         # wind-direction coefficient
    a_slope: float = 0.078    # slope coefficient (per degree)
    burn_steps: int = 1       # timesteps a cell stays BURNING before BURNED
    cell_size_m: float = 100.0  # ground size of one cell, metres


# --- low level helpers ------------------------------------------------------
def _neighbor(arr: np.ndarray, di: int, dj: int) -> np.ndarray:
    """Return B where ``B[i, j] = arr[i + di, j + dj]``.

    Cells whose neighbour would fall outside the grid are filled with 0
    (i.e. no fire / no contribution comes from beyond the border).
    """
    h, w = arr.shape
    out = np.zeros_like(arr)
    # destination / source slices for a shift of (di, dj) on each axis
    di_dst = slice(max(0, -di), min(h, h - di))
    di_src = slice(max(0, di), min(h, h + di))
    dj_dst = slice(max(0, -dj), min(w, w - dj))
    dj_src = slice(max(0, dj), min(w, w + dj))
    out[di_dst, dj_dst] = arr[di_src, dj_src]
    return out


def _ignition_mask(ignition, shape: tuple[int, int], nonflammable: np.ndarray) -> np.ndarray:
    """Build a boolean ignition mask from a boolean array or a list of (i, j)."""
    h, w = shape
    mask = np.zeros(shape, dtype=bool)
    arr = np.asarray(ignition)
    if arr.dtype == bool and arr.shape == shape:
        mask = arr.copy()
    else:
        for i, j in np.atleast_2d(arr).astype(int):
            if 0 <= i < h and 0 <= j < w:
                mask[i, j] = True
    # never ignite a cell that cannot burn
    mask &= ~nonflammable.astype(bool)
    return mask


def precompute_factors(
    fuel_factor: np.ndarray,
    moisture_factor: np.ndarray,
    elevation: np.ndarray,
    wind_speed: float,
    wind_dir_deg: float,
    params: CAParams,
) -> list[tuple[int, int, np.ndarray]]:
    """Pre-compute the *static* per-direction spread probability P(s->t).

    Wind is uniform and fuel / moisture / terrain are constant during a run,
    so ``p0 * p_fuel * p_moist * p_wind * p_slope`` only depends on the
    neighbour direction and can be computed once and reused every timestep.

    Returns a list of ``(di, dj, P_static)`` where ``P_static`` is a 2-D array
    giving, for every target cell, the ignition probability *if* the neighbour
    in direction (di, dj) is currently burning.
    """
    # Direction the wind BLOWS towards (opposite of meteorological "from").
    blow_bearing = math.radians((wind_dir_deg + 180.0) % 360.0)
    wind_north = math.cos(blow_bearing)   # north component of wind-blow unit vector
    wind_east = math.sin(blow_bearing)    # east  component

    out: list[tuple[int, int, np.ndarray]] = []
    for di, dj in _DIRS:
        dlen = math.hypot(di, dj)  # 1 for orthogonal, sqrt(2) for diagonal
        # Spread direction s -> t expressed as a geographic unit vector.
        # Source s sits at offset (di, dj) from target t, so the fire travels
        # along (t - s) = (-di, -dj) in grid space. Map to (north, east):
        # +i = south => north = -(-di) = di ; +j = east => east = -dj.
        spread_north = di / dlen
        spread_east = -dj / dlen
        cos_theta = spread_north * wind_north + spread_east * wind_east

        # Wind factor: downwind (cos=1) -> exp(c1 V); upwind (cos=-1) -> tiny.
        wind_f = math.exp(params.c1 * wind_speed) * math.exp(
            params.c2 * wind_speed * (cos_theta - 1.0)
        )

        # Slope factor: phi = atan(rise / run) between source and target.
        dist = params.cell_size_m * dlen
        rise = elevation - _neighbor(elevation, di, dj)  # target minus source
        phi_deg = np.degrees(np.arctan2(rise, dist))
        slope_f = np.exp(params.a_slope * phi_deg)

        p_static = np.clip(
            params.p0 * fuel_factor * moisture_factor * wind_f * slope_f,
            0.0,
            1.0,
        )
        out.append((di, dj, p_static))
    return out


def _step(
    state: np.ndarray,
    timer: np.ndarray,
    factors: Sequence[tuple[int, int, np.ndarray]],
    params: CAParams,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Advance the automaton one timestep. Returns (new_state, new_timer)."""
    burning = state == BURNING

    # Probability a cell survives (is NOT ignited) this step = product over
    # directions of (1 - P) for every direction whose neighbour is burning.
    survive = np.ones(state.shape, dtype=np.float64)
    for di, dj, p_static in factors:
        src_burning = _neighbor(burning, di, dj)  # is neighbour (di,dj) on fire?
        survive *= 1.0 - p_static * src_burning
    p_ignite = 1.0 - survive

    new_fire = (state == UNBURNED) & (rng.random(state.shape) < p_ignite)

    # Burn-out bookkeeping: currently burning cells age by one step; those that
    # have burned for `burn_steps` become BURNED.
    timer = timer.copy()
    timer[burning] -= 1
    burned_now = burning & (timer <= 0)

    state = state.copy()
    state[burned_now] = BURNED
    state[new_fire] = BURNING
    timer[new_fire] = params.burn_steps
    return state, timer


def simulate_once(
    fuel_factor: np.ndarray,
    moisture_factor: np.ndarray,
    elevation: np.ndarray,
    nonflammable: np.ndarray,
    ignition,
    wind_speed: float,
    wind_dir_deg: float,
    *,
    n_steps: int = 60,
    params: CAParams | None = None,
    seed: int | None = None,
    factors: Sequence[tuple[int, int, np.ndarray]] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run a single stochastic spread realisation.

    Returns ``(final_state, burned_history)`` where ``burned_history`` has
    shape ``(n_steps, H, W)`` and is True wherever a cell is BURNING or BURNED
    at that timestep (i.e. cumulative burned area through time).
    """
    params = params or CAParams()
    nonflam = nonflammable.astype(bool)
    if factors is None:
        factors = precompute_factors(
            fuel_factor, moisture_factor, elevation, wind_speed, wind_dir_deg, params
        )
    rng = np.random.default_rng(seed)

    state = np.where(nonflam, NONFLAMMABLE, UNBURNED).astype(np.int8)
    ign = _ignition_mask(ignition, state.shape, nonflam)
    state[ign] = BURNING
    timer = np.where(state == BURNING, params.burn_steps, 0).astype(np.int16)

    history = np.empty((n_steps, *state.shape), dtype=bool)
    for t in range(n_steps):
        state, timer = _step(state, timer, factors, params, rng)
        history[t] = (state == BURNING) | (state == BURNED)
    return state, history


def simulate_montecarlo(
    fuel_factor: np.ndarray,
    moisture_factor: np.ndarray,
    elevation: np.ndarray,
    nonflammable: np.ndarray,
    ignition,
    wind_speed: float,
    wind_dir_deg: float,
    *,
    n_runs: int = 30,
    n_steps: int = 60,
    params: CAParams | None = None,
    seed: int = 0,
) -> dict:
    """Run the CA ``n_runs`` times and average into a burn-probability map.

    Because the spread is stochastic, a single run is noisy. Averaging many
    independent runs (Monte Carlo) yields, for each cell, the fraction of runs
    in which it ended up burnt = an estimate of its burn probability.

    Returns a dict:
      burn_prob : (H, W) float in [0, 1] - final burn probability per cell.
      frames    : (n_steps, H, W) float in [0, 1] - burn probability through
                  time, for animating the spread.
      ignition, wind_speed, wind_dir_deg, n_runs, n_steps : echoed inputs.
    """
    params = params or CAParams()
    h, w = fuel_factor.shape
    # Static spread factors are identical across runs -> compute once.
    factors = precompute_factors(
        fuel_factor, moisture_factor, elevation, wind_speed, wind_dir_deg, params
    )

    frames_accum = np.zeros((n_steps, h, w), dtype=np.float64)
    # Independent, reproducible RNG stream per run.
    child_seeds = np.random.SeedSequence(seed).spawn(n_runs)
    for r in range(n_runs):
        _, history = simulate_once(
            fuel_factor,
            moisture_factor,
            elevation,
            nonflammable,
            ignition,
            wind_speed,
            wind_dir_deg,
            n_steps=n_steps,
            params=params,
            seed=child_seeds[r],
            factors=factors,
        )
        frames_accum += history

    frames = frames_accum / float(n_runs)
    burn_prob = frames[-1].copy()  # cumulative burned fraction at the last step
    return {
        "burn_prob": burn_prob,
        "frames": frames,
        "ignition": ignition,
        "wind_speed": wind_speed,
        "wind_dir_deg": wind_dir_deg,
        "n_runs": n_runs,
        "n_steps": n_steps,
    }
