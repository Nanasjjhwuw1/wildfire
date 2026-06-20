"""Logic tests for the cellular-automata fire-spread engine.

These assert the *physics* of the model rather than exact numbers:
  - fire cannot enter non-flammable cells,
  - with zero base probability nothing spreads,
  - a strong steady wind biases spread downwind,
  - on flat ground with no wind, fire climbs uphill faster than down,
  - burn probabilities stay in [0, 1] and the ignition point always burns.
"""

import numpy as np

from backend.models.spread_ca import (
    BURNED,
    BURNING,
    NONFLAMMABLE,
    CAParams,
    simulate_montecarlo,
    simulate_once,
)


def _flat_inputs(h=61, w=61):
    fuel = np.ones((h, w), dtype=float)
    moist = np.ones((h, w), dtype=float)
    elev = np.zeros((h, w), dtype=float)
    nonflam = np.zeros((h, w), dtype=bool)
    return fuel, moist, elev, nonflam


def test_burn_prob_in_range_and_ignition_burns():
    fuel, moist, elev, nonflam = _flat_inputs()
    c = 30
    out = simulate_montecarlo(
        fuel, moist, elev, nonflam, [(c, c)], wind_speed=3, wind_dir_deg=0,
        n_runs=12, n_steps=20, seed=1,
    )
    bp = out["burn_prob"]
    assert bp.min() >= 0.0 and bp.max() <= 1.0
    # The ignition cell burns in every run.
    assert bp[c, c] == 1.0
    # Frames are monotonically non-decreasing (cumulative burned area).
    diffs = np.diff(out["frames"], axis=0)
    assert diffs.min() >= -1e-9


def test_nonflammable_never_burns_and_blocks_spread():
    fuel, moist, elev, nonflam = _flat_inputs()
    h, w = fuel.shape
    # A full vertical wall of water splits the grid in two.
    wall = w // 2
    nonflam[:, wall] = True
    out = simulate_montecarlo(
        fuel, moist, elev, nonflam, [(h // 2, wall - 5)],
        wind_speed=0, wind_dir_deg=0, n_runs=10, n_steps=60, seed=2,
    )
    bp = out["burn_prob"]
    # The wall itself never catches fire...
    assert np.all(bp[:, wall] == 0.0)
    # ...and fire ignited on the left cannot reach the far right side.
    assert np.all(bp[:, wall + 1:] == 0.0)


def test_zero_base_probability_no_spread():
    fuel, moist, elev, nonflam = _flat_inputs()
    c = 30
    params = CAParams(p0=0.0)
    state, _ = simulate_once(
        fuel, moist, elev, nonflam, [(c, c)], wind_speed=10, wind_dir_deg=270,
        n_steps=30, params=params, seed=3,
    )
    burnt = (state == BURNING) | (state == BURNED)
    # Only the ignition cell is ever affected; nothing propagates.
    assert burnt.sum() == 1
    assert burnt[c, c]


def test_strong_wind_biases_spread_downwind():
    fuel, moist, elev, nonflam = _flat_inputs(81, 81)
    c = 40
    # Wind FROM the west (270 deg) blows toward the EAST.
    out = simulate_montecarlo(
        fuel, moist, elev, nonflam, [(c, c)], wind_speed=12, wind_dir_deg=270,
        n_runs=20, n_steps=28, seed=4,
    )
    bp = out["burn_prob"]
    east = bp[:, c + 1:].sum()   # downwind half
    west = bp[:, :c].sum()       # upwind half
    assert east > 2.0 * west, f"expected strong eastward bias, got E={east:.1f} W={west:.1f}"


def test_fire_climbs_uphill_faster_than_downhill():
    fuel, moist, _, nonflam = _flat_inputs(81, 81)
    h, w = fuel.shape
    c = 40
    # Elevation ramp: high in the NORTH (row 0), low in the SOUTH.
    # 20 m rise per 100 m cell -> ~11 deg slope.
    rows = np.arange(h)[:, None]
    elev = (h - 1 - rows) * 20.0 * np.ones((1, w))
    out = simulate_montecarlo(
        fuel, moist, elev, nonflam, [(c, c)], wind_speed=0, wind_dir_deg=0,
        n_runs=20, n_steps=22, seed=5,
    )
    bp = out["burn_prob"]
    uphill = bp[:c, :].sum()      # north of ignition = higher ground
    downhill = bp[c + 1:, :].sum()  # south of ignition = lower ground
    assert uphill > 1.3 * downhill, f"expected uphill bias, up={uphill:.1f} down={downhill:.1f}"
