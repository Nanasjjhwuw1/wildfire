"""Tests for the wildfire CO2-emissions estimate."""

import numpy as np

from backend.models.emissions import EF_CO2, estimate_emissions


def test_single_forest_cell():
    bp = np.zeros((3, 3))
    bp[1, 1] = 1.0                      # one cell certain to burn
    lc = np.full((3, 3), 10)           # all tree cover (1.2 kg/m^2)
    em = estimate_emissions(bp, lc, 1e6)  # 1 km^2 cells

    assert em["burned_area_ha"] == 100.0          # 1e6 m^2 = 100 ha
    assert abs(em["dry_matter_tonnes"] - 1200.0) < 1e-6   # 1e6 * 1.2 / 1000
    assert abs(em["co2_tonnes"] - 1.2e6 * EF_CO2 / 1000) < 1e-3


def test_nonvegetated_emits_nothing():
    bp = np.ones((2, 2))
    lc = np.full((2, 2), 80)           # water -> no fuel
    em = estimate_emissions(bp, lc, 1e6)
    assert em["co2_tonnes"] == 0.0
    assert em["dry_matter_tonnes"] == 0.0


def test_more_burn_more_co2_and_inside_mask():
    lc = np.full((2, 2), 10)
    small = estimate_emissions(np.full((2, 2), 0.2), lc, 1e6)
    big = estimate_emissions(np.full((2, 2), 0.8), lc, 1e6)
    assert big["co2_tonnes"] > small["co2_tonnes"]

    inside = np.array([[True, False], [False, False]])
    masked = estimate_emissions(np.ones((2, 2)), lc, 1e6, inside=inside)
    assert masked["burned_area_ha"] == 100.0      # only the 1 in-province cell
