"""
emissions.py - Estimate wildfire carbon (CO2) emissions from a simulated burn.

Standard biomass-burning method (Seiler & Crutzen 1980; IPCC 2006 AFOLU
Guidelines; used by GFED):

    emission = burned_area  x  fuel_consumed  x  emission_factor

We use the per-cell burn probability from the Monte-Carlo CA as the EXPECTED
burned area (sum of p * cell_area), and a per-land-cover fuel-consumption value
- dry matter actually consumed, kg/m^2, which folds fuel load x combustion
completeness - tuned for the mixed-deciduous / dry-dipterocarp forest that
dominates northern-Thailand (Chiang Mai) fires.
"""

from __future__ import annotations

import numpy as np

# Dry matter consumed by a surface fire, by ESA WorldCover class (kg/m^2).
# (e.g. 1.2 kg/m^2 = 12 tonnes/ha for forest.) Other classes -> 0.
FUEL_CONSUMPTION = {
    10: 1.2,   # tree cover  (forest surface fire)
    20: 0.8,   # shrubland
    30: 0.4,   # grassland
    40: 0.5,   # cropland    (crop-residue burning)
}
EF_CO2 = 1.58           # kg CO2 per kg dry matter (IPCC 2006, tropical forest)
_CAR_T_PER_YEAR = 4.6   # avg passenger car, t CO2/yr (US EPA) - a relatable scale


def consumption_grid(landcover: np.ndarray) -> np.ndarray:
    """Map a WorldCover class grid to dry-matter consumption (kg/m^2)."""
    g = np.zeros(np.shape(landcover), dtype=float)
    lc = np.asarray(landcover)
    for cls, val in FUEL_CONSUMPTION.items():
        g[lc == cls] = val
    return g


def estimate_emissions(burn_prob, landcover, cell_area_m2: float, inside=None) -> dict:
    """Expected CO2 emissions for a simulated burn.

    ``burn_prob`` is the CA burn-probability grid; ``inside`` (optional bool
    grid) restricts the accounting to cells inside the province.
    """
    bp = np.asarray(burn_prob, dtype=float)
    if inside is not None:
        bp = bp * np.asarray(inside, dtype=float)
    area_w = bp * float(cell_area_m2)                      # expected burned m^2/cell
    dm_kg = float((area_w * consumption_grid(landcover)).sum())
    co2_t = dm_kg * EF_CO2 / 1000.0
    burned_ha = float(area_w.sum()) / 1e4
    return {
        "co2_tonnes": round(co2_t, 1),
        "dry_matter_tonnes": round(dm_kg / 1000.0, 1),
        "burned_area_ha": round(burned_ha, 1),
        "burned_area_rai": round(burned_ha * 6.25),       # 1 ha = 6.25 rai (Thai)
        "car_years_equiv": round(co2_t / _CAR_T_PER_YEAR),
        "ef_co2": EF_CO2,
    }
