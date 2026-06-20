"""
risk_fwi.py - Fire risk from the Canadian Fire Weather Index (FWI) system.

We implement the standard FFMC (Fine Fuel Moisture Code) and ISI (Initial
Spread Index) equations from:

  Van Wagner, C.E. & Pickett, T.L. (1985). "Equations and FORTRAN program for
  the Canadian Forest Fire Weather Index System." Can. For. Serv. Forestry
  Tech. Report 33.

These take live weather (temperature, relative humidity, wind, 24 h rain) and
output the dryness of fine fuels (FFMC) and how readily a fire would spread
(ISI). Both are computed *per grid cell* using the interpolated weather field,
so the risk map reflects real conditions - not random numbers.

The final 0..1 risk map combines the fire-weather danger with the landscape:

    risk = f(ISI) * fuel_boost * slope_boost * aspect_boost

  f(ISI)        regional fire-weather danger, saturating in [0,1]
  fuel_boost    more fuel (forest/shrub) -> higher risk than grass/crop
  slope_boost   steeper ground -> faster potential spread
  aspect_boost  sun-facing (SW) slopes dry out -> slightly higher risk

The map is min-max normalised over flammable cells for display; non-flammable
cells (water/built-up) are forced to 0. A scalar danger class (Low..Extreme)
is also returned for the legend.
"""

from __future__ import annotations

import numpy as np

from backend.data.grid import Grid


# --------------------------------------------------------------------------
# FFMC - Fine Fuel Moisture Code (Van Wagner & Pickett 1985), vectorised.
# Works element-wise so temp/rh can be 2-D grids.
# --------------------------------------------------------------------------
def ffmc(temp, rh, wind_kmh, rain, ffmc_prev: float = 85.0):
    T = np.asarray(temp, dtype=float)
    H = np.clip(np.asarray(rh, dtype=float), 0.0, 100.0)
    W = np.asarray(wind_kmh, dtype=float)
    ro = np.asarray(rain, dtype=float)
    W, ro = np.broadcast_to(W, T.shape), np.broadcast_to(ro, T.shape)

    # previous day's fine-fuel moisture content from previous FFMC
    mo = np.full(T.shape, 147.2 * (101.0 - ffmc_prev) / (59.5 + ffmc_prev))

    # --- rainfall wetting -------------------------------------------------
    rain_mask = ro > 0.5
    rf = np.where(rain_mask, ro - 0.5, 0.0)
    safe_rf = np.where(rf > 0, rf, 1.0)  # avoid div-by-zero in exp(-6.93/rf)
    mr = mo + 42.5 * rf * np.exp(-100.0 / (251.0 - mo)) * (1.0 - np.exp(-6.93 / safe_rf))
    mr = np.where(mo > 150.0, mr + 0.0015 * (mo - 150.0) ** 2 * np.sqrt(rf), mr)
    mr = np.minimum(mr, 250.0)
    mo = np.where(rain_mask, mr, mo)

    # --- drying / wetting toward equilibrium moisture content -------------
    Ed = 0.942 * H ** 0.679 + 11.0 * np.exp((H - 100.0) / 10.0) \
        + 0.18 * (21.1 - T) * (1.0 - np.exp(-0.115 * H))
    ko = 0.424 * (1.0 - (H / 100.0) ** 1.7) + 0.0694 * np.sqrt(W) * (1.0 - (H / 100.0) ** 8)
    kd = ko * 0.581 * np.exp(0.0365 * T)
    m_dry = Ed + (mo - Ed) * 10.0 ** (-kd)

    Ew = 0.618 * H ** 0.753 + 10.0 * np.exp((H - 100.0) / 10.0) \
        + 0.18 * (21.1 - T) * (1.0 - np.exp(-0.115 * H))
    kl = 0.424 * (1.0 - ((100.0 - H) / 100.0) ** 1.7) \
        + 0.0694 * np.sqrt(W) * (1.0 - ((100.0 - H) / 100.0) ** 8)
    kw = kl * 0.581 * np.exp(0.0365 * T)
    m_wet = Ew - (Ew - mo) * 10.0 ** (-kw)

    m = np.where(mo > Ed, m_dry, np.where(mo < Ew, m_wet, mo))
    F = 59.5 * (250.0 - m) / (147.2 + m)
    return np.clip(F, 0.0, 101.0)


def isi(ffmc_val, wind_kmh):
    """Initial Spread Index from FFMC and wind speed (km/h)."""
    F = np.asarray(ffmc_val, dtype=float)
    W = np.broadcast_to(np.asarray(wind_kmh, dtype=float), F.shape)
    m = 147.2 * (101.0 - F) / (59.5 + F)             # fine-fuel moisture content
    f_wind = np.exp(0.05039 * W)                     # wind effect on spread
    f_fuel = 91.9 * np.exp(-0.1386 * m) * (1.0 + m ** 5.31 / 4.93e7)  # moisture effect
    return 0.208 * f_wind * f_fuel


def moisture_factor_from_ffmc(ffmc_arr):
    """Map FFMC (0..101, higher = drier fine fuels) to a CA spread multiplier in
    (0, 1]. Wet fuels (low FFMC) strongly damp spread; bone-dry fuels ~= 1.0.
    This is how live weather feeds the cellular-automata moisture term.
    """
    return np.clip(np.asarray(ffmc_arr, dtype=float) / 85.0, 0.05, 1.0)


def _danger_class(isi_scalar: float) -> str:
    # Illustrative ISI breakpoints for a 5-level danger rating.
    for thr, label in [(2, "Low"), (5, "Moderate"), (8, "High"), (13, "Very High")]:
        if isi_scalar < thr:
            return label
    return "Extreme"


def compute_risk(grid: Grid, *, weather=None, terrain=None, fuel=None) -> dict:
    """Compute the georeferenced fire-risk map and summary indices.

    Returns: risk (2-D 0..1), ffmc (2-D), isi (2-D), plus scalar ffmc/isi and a
    danger_class string for the area.
    """
    from backend.data import fuel as fuel_mod
    from backend.data import terrain as terrain_mod
    from backend.data import weather as weather_mod

    weather = weather or weather_mod.get_area_weather(grid)
    terrain = terrain or terrain_mod.get_terrain(grid)
    fuel = fuel or fuel_mod.get_fuel(grid)

    wfields = weather_mod.weather_to_grid(grid, weather)
    wind_kmh = wfields["wind_speed"] * 3.6  # m/s -> km/h for the FWI equations

    ffmc_grid = ffmc(wfields["temp_c"], wfields["rh"], wind_kmh, wfields["rain_24h"])
    isi_grid = isi(ffmc_grid, wind_kmh)

    # regional fire-weather danger, saturating: ISI ~10 -> ~0.7
    risk_weather = 1.0 - np.exp(-isi_grid / 8.0)

    # landscape modulation
    fuel_norm = np.clip(fuel["fuel_factor"] / 1.3, 0.0, 1.0)
    slope_norm = np.clip(terrain["slope_deg"] / 45.0, 0.0, 1.0)
    # SW-facing (~202.5 deg) slopes get the most afternoon sun -> driest
    aspect_dry = 0.5 + 0.5 * np.cos(np.radians(terrain["aspect_deg"] - 202.5))

    fuel_boost = 0.5 + fuel_norm            # 0.5 .. 1.5
    slope_boost = 0.8 + 0.5 * slope_norm    # 0.8 .. 1.3
    aspect_boost = 0.85 + 0.3 * aspect_dry  # 0.85 .. 1.15

    # Absolute risk (NOT peak-normalised): a wet/low-danger day genuinely reads
    # low across the whole map, a hot/dry/windy day reads high. The landscape
    # boosts only shape the spatial pattern within that level.
    risk = np.clip(risk_weather * fuel_boost * slope_boost * aspect_boost, 0.0, 1.0)
    risk[fuel["nonflammable"]] = 0.0

    rep = weather["representative"]
    rep_wind_kmh = rep["wind_speed"] * 3.6
    rep_ffmc = float(ffmc(rep["temp"], rep["rh"], rep_wind_kmh, rep["rain_24h"]))
    rep_isi = float(isi(rep_ffmc, rep_wind_kmh))

    return {
        "risk": risk,
        "ffmc": ffmc_grid,
        "isi": isi_grid,
        "ffmc_scalar": round(rep_ffmc, 1),
        "isi_scalar": round(rep_isi, 2),
        "danger_class": _danger_class(rep_isi),
        "weather": rep,
    }
