"""
app.py - FastAPI backend for the wildfire MVP.

Endpoints
  GET  /api/health             liveness
  GET  /api/area               area metadata + bbox + latest real wind
  GET  /api/risk               FWI risk map (PNG overlay + bounds + indices)
  POST /api/simulate           CA Monte-Carlo spread from a clicked ignition
  GET  /api/recommend          (Slice 5) suppression zones + firebreaks
  GET  /api/firepoints         (Slice 5) historical FIRMS hotspots (if key set)

Design notes
  * Terrain & fuel never change -> loaded once and cached in memory.
  * Weather is cached on disk with a TTL (see data/weather.py); risk is cheap
    so it's computed per request from the cached layers.
  * All inputs are validated (pydantic + bbox check); data-source failures are
    turned into clean 503 responses instead of stack traces.
"""

from __future__ import annotations

import pathlib
import time
import uuid

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend import config, render
from backend.data import aoi as aoi_mod
from backend.data import firms as firms_mod
from backend.data import weather as weather_mod
from backend.data.grid import Grid
from backend.models.emissions import estimate_emissions
from backend.models.recommend import recommend as build_recommendation
from backend.models.risk_fwi import compute_risk, ffmc, moisture_factor_from_ffmc
from backend.models.spread_ca import CAParams, simulate_montecarlo

app = FastAPI(title="Wildfire MVP API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon: open CORS so the Vite dev server can call us
    allow_methods=["*"],
    allow_headers=["*"],
)

GRID = Grid.from_config()
_LAYER_CACHE: dict[str, dict] = {}   # keyed by DATA_MODE so tests (mock) stay isolated
_OUTSIDE_CACHE: dict[str, np.ndarray] = {}  # province-clip mask, per data mode
SIMS: dict[str, dict] = {}           # sim_id -> stored simulation (for /recommend)
_MAX_SIMS = 25


def get_outside() -> np.ndarray:
    """Boolean grid (True = outside the province) for clipping overlays to the
    real Chiang Mai boundary instead of the rectangular bbox."""
    key = config.DATA_MODE
    if key not in _OUTSIDE_CACHE:
        _OUTSIDE_CACHE[key] = aoi_mod.outside_mask(GRID)
    return _OUTSIDE_CACHE[key]


# --------------------------------------------------------------------------
# layer access (lazy + cached)
# --------------------------------------------------------------------------
def get_layers() -> dict:
    """Terrain + fuel for the grid, loaded once per data mode."""
    key = config.DATA_MODE
    if key not in _LAYER_CACHE:
        from backend.data import fuel as fuel_mod
        from backend.data import terrain as terrain_mod

        try:
            _LAYER_CACHE[key] = {
                "terrain": terrain_mod.get_terrain(GRID),
                "fuel": fuel_mod.get_fuel(GRID),
            }
        except Exception as exc:  # network / data failure
            raise HTTPException(503, f"failed to load terrain/fuel data: {exc}") from exc
    return _LAYER_CACHE[key]


def get_weather() -> dict:
    try:
        return weather_mod.get_area_weather(GRID)
    except Exception as exc:
        raise HTTPException(503, f"failed to load weather: {exc}") from exc


# --------------------------------------------------------------------------
# request models
# --------------------------------------------------------------------------
class SimRequest(BaseModel):
    lat: float = Field(..., description="ignition latitude (WGS84)")
    lon: float = Field(..., description="ignition longitude (WGS84)")
    wind_speed: float | None = Field(None, ge=0, le=60, description="m/s; default = live area wind")
    wind_direction: float | None = Field(None, ge=0, le=360, description="deg FROM; default = live")
    fuel_dryness: float | None = Field(
        None, ge=0, le=1,
        description="0=soaked .. 1=bone dry; default = derived from live-weather FFMC",
    )
    n_runs: int = Field(config.DEFAULT_N_RUNS, ge=1, le=config.MAX_N_RUNS)
    n_steps: int = Field(config.DEFAULT_N_STEPS, ge=1, le=config.MAX_N_STEPS)


# --------------------------------------------------------------------------
# endpoints
# --------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "data_mode": config.DATA_MODE}


@app.get("/api/area")
def area():
    wx = get_weather()
    return {
        "area_name": config.AREA_NAME,
        "grid": GRID.as_dict(),
        "bbox": list(config.BBOX),
        "bounds": GRID.leaflet_bounds(),
        "weather": {**wx["representative"], "source": wx.get("source"),
                    "fetched_at": wx.get("fetched_at")},
        "assets": config.ASSETS,
        "firms_enabled": bool(config.FIRMS_API_KEY),
        "aoi_geojson": aoi_mod.province_geojson(),  # real province border (not the bbox)
    }


@app.get("/api/risk")
def risk():
    layers = get_layers()
    wx = get_weather()
    r = compute_risk(GRID, weather=wx, terrain=layers["terrain"], fuel=layers["fuel"])
    return {
        "bounds": GRID.leaflet_bounds(),
        "image": render.overlay_png(r["risk"], cmap="YlOrRd",
                                    mask=layers["fuel"]["nonflammable"] | get_outside(),
                                    hide_below=0.05),
        "danger_class": r["danger_class"],
        "ffmc": r["ffmc_scalar"],
        "isi": r["isi_scalar"],
        "weather": {**r["weather"], "source": wx.get("source")},
        "legend": {"0": "low", "0.5": "moderate", "1": "extreme"},
    }


@app.post("/api/simulate")
def simulate(req: SimRequest):
    # --- validate ignition is inside the study area ---
    if not GRID.contains(req.lon, req.lat):
        raise HTTPException(
            422,
            f"ignition ({req.lat}, {req.lon}) is outside the study area bbox {list(config.BBOX)}",
        )

    layers = get_layers()
    wx = get_weather()
    fuel = layers["fuel"]
    terrain = layers["terrain"]

    # Default wind = live area wind; user override wins if provided.
    rep = wx["representative"]
    wind_speed = req.wind_speed if req.wind_speed is not None else rep["wind_speed"]
    wind_dir = req.wind_direction if req.wind_direction is not None else rep["wind_dir"]
    wind_source = "user" if req.wind_speed is not None else "live"

    # Fuel-moisture term for the CA. Default = derived from live-weather FFMC;
    # a user dryness override (0..1) lets a demo show dry-season behaviour.
    if req.fuel_dryness is not None:
        moisture = np.full(GRID.shape, float(np.clip(req.fuel_dryness, 0.05, 1.0)))
        moisture_source = "user"
    else:
        wfields = weather_mod.weather_to_grid(GRID, wx)
        ff = ffmc(wfields["temp_c"], wfields["rh"], wfields["wind_speed"] * 3.6, wfields["rain_24h"])
        moisture = moisture_factor_from_ffmc(ff)
        moisture_source = "live"

    row, col = GRID.lonlat_to_rowcol(req.lon, req.lat)
    if fuel["nonflammable"][row, col]:
        raise HTTPException(
            422, f"ignition cell is non-flammable (water/built-up) at ({req.lat}, {req.lon})"
        )

    out = simulate_montecarlo(
        fuel["fuel_factor"], moisture, terrain["elevation"], fuel["nonflammable"],
        [(row, col)], wind_speed, wind_dir,
        n_runs=req.n_runs, n_steps=req.n_steps,
        params=CAParams(cell_size_m=GRID.cell_size_m),
    )
    burn_prob = out["burn_prob"]
    frames = out["frames"]
    outside = get_outside()
    clip = fuel["nonflammable"] | outside  # hide non-fuel + outside-province

    emissions = estimate_emissions(
        burn_prob, fuel["landcover"], GRID.cell_width_m * GRID.cell_height_m, inside=~outside
    )

    # subsample frames so the animation payload stays small (<= ~30 frames)
    stride = max(1, int(np.ceil(req.n_steps / 30)))
    frame_urls = [
        render.overlay_png(frames[t], cmap="inferno", mask=clip, hide_below=0.03)
        for t in range(0, req.n_steps, stride)
    ]

    sim_id = uuid.uuid4().hex[:12]
    SIMS[sim_id] = {
        "burn_prob": burn_prob,
        "ignition_rc": (row, col),
        "ignition_lonlat": (req.lon, req.lat),
        "wind_speed": wind_speed,
        "wind_dir": wind_dir,
        "created": time.time(),
    }
    if len(SIMS) > _MAX_SIMS:  # evict oldest
        oldest = min(SIMS, key=lambda k: SIMS[k]["created"])
        del SIMS[oldest]

    flammable = ~fuel["nonflammable"]
    return {
        "sim_id": sim_id,
        "bounds": GRID.leaflet_bounds(),
        "ignition": {"lat": req.lat, "lon": req.lon, "row": row, "col": col},
        "wind": {"speed": round(float(wind_speed), 2), "direction": round(float(wind_dir), 1),
                 "source": wind_source},
        "fuel_moisture": {"mean_factor": round(float(moisture.mean()), 3), "source": moisture_source},
        "n_runs": req.n_runs,
        "n_steps": req.n_steps,
        "burn_prob_image": render.overlay_png(burn_prob, cmap="inferno",
                                              mask=clip, hide_below=0.03),
        "frames": frame_urls,
        "stats": {
            "burned_fraction": round(float(burn_prob[flammable].mean()), 4),
            "max_burn_prob": round(float(burn_prob.max()), 3),
        },
        "emissions": emissions,
    }


@app.get("/api/recommend")
def recommend_zones(sim_id: str):
    sim = SIMS.get(sim_id)
    if sim is None:
        raise HTTPException(404, f"unknown sim_id '{sim_id}' (run /api/simulate first)")
    layers = get_layers()
    return build_recommendation(
        GRID, sim["burn_prob"], sim["ignition_rc"], sim["wind_dir"],
        fuel=layers["fuel"], assets=config.ASSETS,
    )


@app.get("/api/firepoints")
def firepoints():
    try:
        return firms_mod.get_firepoints(GRID)
    except Exception as exc:
        raise HTTPException(503, f"FIRMS fetch failed: {exc}") from exc


@app.get("/api/risk_ml")
def risk_ml():
    """ML fire-susceptibility layer (trained on historical FIRMS fires)."""
    from backend.models import risk_ml as ml_mod

    if not ml_mod.model_available():
        raise HTTPException(
            503, "ML model not trained yet — run scripts/train_risk_model.py (needs FIRMS_API_KEY)"
        )
    layers = get_layers()
    try:
        out = ml_mod.predict_risk_grid(GRID, terrain=layers["terrain"], fuel=layers["fuel"])
    except Exception as exc:
        raise HTTPException(503, f"ML inference failed: {exc}") from exc
    return {
        "bounds": GRID.leaflet_bounds(),
        "image": render.overlay_png(out["risk"], cmap="cool",
                                    mask=layers["fuel"]["nonflammable"] | get_outside(),
                                    hide_below=0.05),
        "metrics": out["metrics"],
        "feature_names": out["feature_names"],
        "trained": True,
    }


@app.get("/api/national")
def national():
    """National AI fire-susceptibility map for Thailand (built by scripts/national_risk_map.py)."""
    import json

    risk_f = config.CACHE_DIR / "national_risk.npy"
    meta_f = config.CACHE_DIR / "national_meta.json"
    if not risk_f.exists() or not meta_f.exists():
        raise HTTPException(503, "national map not built yet (run scripts/national_risk_map.py)")
    arr = np.load(risk_f)
    meta = json.loads(meta_f.read_text())
    return {
        "bounds": meta["bounds"],
        "image": render.overlay_png(arr, cmap="YlOrRd", hide_below=0.06),
        "metrics": {k: meta[k] for k in ("auc", "n_pos", "n_fires", "cell_km", "importances") if k in meta},
    }


# Serve the built frontend from the same server (single-container deploy).
# Registered LAST so /api/* routes always take precedence. Skipped in local dev
# where frontend/dist doesn't exist (the Vite dev server serves the UI instead).
_DIST = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
