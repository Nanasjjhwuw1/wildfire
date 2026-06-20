"""Tests for the FWI fire-risk model.

Checks the FFMC/ISI equations against a known reference value and asserts the
physically expected monotonic responses, plus that the risk map is well-formed.
"""

import numpy as np

from backend.config import GRID_COLS, GRID_ROWS
from backend.models.risk_fwi import compute_risk, ffmc, isi


def test_ffmc_reference_value():
    # Standard Van Wagner & Pickett worked example:
    # T=17C, RH=42%, wind=25 km/h, rain=0, previous FFMC=85 -> FFMC ~= 87.7
    val = float(ffmc(17.0, 42.0, 25.0, 0.0, ffmc_prev=85.0))
    assert abs(val - 87.7) < 1.0, f"FFMC {val} not near reference 87.7"


def test_ffmc_monotonic_responses():
    base = float(ffmc(25.0, 40.0, 10.0, 0.0))
    # Lower humidity -> drier fine fuels -> higher FFMC
    assert float(ffmc(25.0, 20.0, 10.0, 0.0)) > base
    # Rain wets fuels -> lower FFMC
    assert float(ffmc(25.0, 40.0, 10.0, 8.0)) < base
    # Higher temperature -> faster drying -> higher FFMC
    assert float(ffmc(35.0, 40.0, 10.0, 0.0)) > base


def test_isi_increases_with_wind_and_ffmc():
    assert float(isi(85.0, 30.0)) > float(isi(85.0, 5.0))   # more wind
    assert float(isi(92.0, 15.0)) > float(isi(80.0, 15.0))  # drier fuel


def test_risk_map_is_wellformed_and_respects_nonflammable():
    # Use mock data so the test needs no network.
    import backend.config as cfg

    old = cfg.DATA_MODE
    cfg.DATA_MODE = "mock"
    try:
        from backend.data.grid import Grid

        grid = Grid.from_config()
        out = compute_risk(grid)
        risk = out["risk"]
        assert risk.shape == (GRID_ROWS, GRID_COLS)
        assert np.isfinite(risk).all()
        assert risk.min() >= 0.0 and risk.max() <= 1.0
        # Non-flammable cells (mock has water + built-up) must be exactly 0.
        from backend.data import mock

        nonflam = mock.mock_fuel(grid)["nonflammable"]
        assert np.all(risk[nonflam] == 0.0)
        assert out["danger_class"] in {"Low", "Moderate", "High", "Very High", "Extreme"}
    finally:
        cfg.DATA_MODE = old
