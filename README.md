# 🔥 Wildfire Risk & Spread — Doi Suthep MVP

An interactive web app that, for one real area (Doi Suthep, Chiang Mai — configurable),
does four things on **real data**:

1. **Fire-risk map** from live weather using the Fire Weather Index (FWI).
2. **Fire-spread simulation** with a cellular automaton (Monte-Carlo) from a point you
   click on the map.
3. **Georeferenced overlays** that sit exactly on the real terrain.
4. **Suppression recommendations** — where to intercept the fire head and where to cut
   firebreaks — derived from the simulation.

Everything is driven by real, free data sources (no API key required for the core loop),
cached to disk so a demo survives flaky/no network.

```
┌──────────────┐    /api/*    ┌───────────────────────────────────────────┐
│ React+Leaflet │ ───────────► │ FastAPI                                    │
│ (nginx :8080) │ ◄─────────── │  risk_fwi (FWI)  spread_ca (CA)  recommend │
└──────────────┘   JSON+PNG    │  data: Open-Meteo · Terrarium DEM · ESA WC │
                                │  disk cache (weather.json, *.npy, tiles)   │
                                └───────────────────────────────────────────┘
```

---

## Quick start (Docker — one command)

```bash
cp .env.example .env        # optional; defaults work out of the box
docker compose up --build
```

- App:     <http://localhost:8080>
- API:     <http://localhost:8000/api/area>

Then **click anywhere on the map** to ignite a fire and watch it spread.

> Tip: run the prefetch first (below) to populate the on-disk cache so the demo works
> even if the venue Wi-Fi dies.
>
> Needs a working Docker daemon. If Docker isn't available on your machine, run the two
> dev servers directly (next section) or use the cloud path under **Deploy** — both serve
> the identical app.

---

## Local development (no Docker)

**Backend** (Python 3.11+; rasterio has wheels for 3.11–3.14):

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
```

**Frontend** (Node 18+):

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api to :8000)
```

**Prefetch real data for an offline demo** (caches weather + DEM + land cover, writes a
preview to `scripts/out/layers.png`):

```bash
python scripts/prefetch.py
```

**Standalone CA demo** (synthetic landscape + animation, proves the spread logic):

```bash
python scripts/demo_ca.py         # writes scripts/out/demo_ca.gif + .png
```

---

## The models (what to say in the pitch)

### 1. Fire risk — Fire Weather Index (`backend/models/risk_fwi.py`)
Implements the standard **FFMC** (Fine Fuel Moisture Code) and **ISI** (Initial Spread
Index) equations (Van Wagner & Pickett 1985) from live temperature, humidity, wind and
24 h rain:

- `FFMC` tracks how dry the fine fuels are (validated against the textbook worked example
  in `tests/test_fwi.py`).
- `ISI = 0.208 · f(wind) · f(moisture)` — how readily a fire would spread.
- The **0–1 risk map** = `f(ISI) × fuel_boost × slope_boost × aspect_boost`: live weather
  sets the danger level, while fuel (land cover), slope and sun-facing aspect shape the
  spatial pattern. Non-flammable cells (water/built-up) are forced to 0.

The risk is **absolute**, so a wet day genuinely reads *Low* and a hot/dry/windy day reads
*Extreme* — it is not normalised to always look red.

### 2. Fire spread — Cellular Automaton (`backend/models/spread_ca.py`)
After Alexandridis et al. (2008). Each cell is `UNBURNED / BURNING / BURNED / NONFLAMMABLE`.
A burning cell ignites a neighbour with probability:

```
P = p0 · p_fuel · p_moist · p_wind(θ) · p_slope(φ)
    p_wind  = exp(c1·V) · exp(c2·V·(cosθ − 1))     # downwind boosted, upwind suppressed
    p_slope = exp(a·φ)                              # uphill spreads faster
```

We run it **N times (Monte-Carlo)** and average to a **burn-probability map** + per-timestep
frames for the animation. Logic is checked in `tests/test_ca.py` (strong wind → biased
downwind; fire climbs uphill faster; non-flammable cells block spread).

### 3. Recommendations (`backend/models/recommend.py`)
From the burn-probability map: finds the **fire head** (high-probability cell furthest
downwind), ranks **suppression zones** on the advancing frontier (weighted toward the head
and toward assets to protect), suggests a **firebreak** perpendicular to the head, and flags
**natural water barriers**. Returned as georeferenced GeoJSON.

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET  | `/api/health` | liveness |
| GET  | `/api/area` | bbox, grid, **live wind**, assets |
| GET  | `/api/risk` | FWI risk PNG overlay + bounds + indices |
| POST | `/api/simulate` | `{lat,lon,wind_speed?,wind_direction?,fuel_dryness?,n_runs?,n_steps?}` → burn-prob overlay + animation frames |
| GET  | `/api/recommend?sim_id=…` | suppression zones + firebreaks (GeoJSON) |
| GET  | `/api/firepoints` | historical FIRMS hotspots (if `FIRMS_API_KEY` set) |

Inputs are validated (pydantic + bbox check → 422); data-source failures become clean 503s;
results are cached (weather TTL in memory + on disk, terrain/land cover as `.npy`).

---

## Data sources (all free)

| Layer | Source | Auth |
|---|---|---|
| Weather | [Open-Meteo](https://open-meteo.com) | none |
| Elevation / slope | [AWS Terrain Tiles (Terrarium)](https://registry.opendata.aws/terrain-tiles/) | none |
| Land cover → fuel | [ESA WorldCover 2021 v200](https://esa-worldcover.org) | none |
| Historical hotspots | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov) | optional key |

## Configuration

Edit `.env` (or `backend/config.py`): `BBOX_*` to move the area, `CELL_SIZE_M` for grid
resolution, `ASSETS` (in `config.py`) for the communities/points to protect, `DATA_MODE=mock`
for fully-offline dev.

## Tests

```bash
pytest backend/tests -q          # CA logic, FWI (incl. reference value), API smoke + recommend
```

## Status — Definition of Done

| # | Criterion | Status |
|---|---|---|
| 1 | One-command run, full loop, no crash | ✅ runs natively (uvicorn + Vite, full loop verified); **`docker compose config` validated + cloud deploy path (Render + Vercel)** below* |
| 2 | Risk map from real weather (Open-Meteo), not random | ✅ FFMC + ISI from live data |
| 3 | Real DEM + slope + real land cover → fuel map | ✅ Terrarium DEM (311–1691 m), ESA WorldCover |
| 4 | Georeferenced overlays (click ignition + heatmap on real ground) | ✅ overlays pinned to the exact bbox |
| 5 | Simulate uses real wind (default) + override; sensible spread | ✅ + fuel-dryness override |
| 6 | Recommendations (suppression zones + firebreaks) from the sim | ✅ GeoJSON; fire head downwind-correct |
| 7 | Caching + input validation + error handling + UI loading/error | ✅ |
| 8 | Disk cache for an offline demo (prefetch) | ✅ `scripts/prefetch.py` |
| 9 | FIRMS hotspot toggle (if key set) | ✅ implemented |
| 10 | README + `.env.example` + deploy notes | ✅ |
| 11 | Basic tests (CA, FWI, API) pass | ✅ 19 passing |

\* The compose stack is complete and `docker compose config` validates. It was not run on the
dev machine because that Docker Desktop install crashes on startup (an unrelated Windows/Docker
bug). Use any host with a working Docker daemon, or the cloud path below — both serve the
identical app.

## Deploy

### Cloud: backend on Render + frontend on Vercel (step by step)

**Backend → Render (Docker):**
1. Push this repo to GitHub.
2. Render → **New → Web Service** → connect the repo.
3. **Runtime: Docker**, Dockerfile path `backend/Dockerfile`, Root Directory `.` (repo root).
4. Environment variables: `DATA_MODE=real` (optionally `FIRMS_API_KEY`, `BBOX_*`,
   `CELL_SIZE_M`, `AREA_NAME`).
5. *(Optional)* add a Render **Disk** mounted at `/app/backend/cache` to persist the data cache.
6. Create the service → copy its URL, e.g. `https://wildfire-api.onrender.com`.
7. Sanity check: open `https://wildfire-api.onrender.com/api/area`.

**Frontend → Vercel (static + API proxy):**
1. Vercel → **New Project** → import the repo, set **Root Directory = `frontend`**.
2. Framework preset **Vite** is auto-detected (build `npm run build`, output `dist`).
3. Point the app's relative `/api` calls at Render: copy `frontend/vercel.json.example` to
   `frontend/vercel.json` and set your backend URL:
   ```json
   { "rewrites": [
     { "source": "/api/:path*", "destination": "https://wildfire-api.onrender.com/api/:path*" }
   ] }
   ```
4. Deploy → you get a public URL, e.g. `https://wildfire.vercel.app`. Share it. ✅

(The backend already sends open CORS headers, so cross-origin calls also work without the
rewrite; the rewrite just keeps everything same-origin under `/api`.)

### Single host (any machine with a working Docker daemon)
```bash
docker compose up --build -d        # app on :8080, API on :8000
python scripts/prefetch.py          # warm the on-disk cache for an offline-safe demo
```
The compose file already mounts `./backend/cache` so prefetched data persists.

## Known limitations (honest)

- Weather is fetched at the bbox corners and interpolated; fine for ~11 km, not for large areas.
- The CA is a probabilistic research model, **not** an operational fire predictor.
- Suggested firebreaks use water/built-up from land cover; roads would need an OSM layer.
- In the wet season real risk is genuinely *Low*; use the **Fuel-dryness** slider to explore
  dry-season scenarios.

## Credits

Alexandridis et al. (2008) CA wildfire model · Van Wagner & Pickett (1985) FWI equations ·
Open-Meteo · AWS Terrain Tiles · ESA WorldCover · NASA FIRMS · OpenStreetMap.
