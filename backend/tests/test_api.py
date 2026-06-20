"""API smoke tests for the FastAPI backend.

Runs entirely in DATA_MODE=mock so no network is needed. Exercises the happy
path of every implemented endpoint plus input-validation failures.
"""

import backend.config as cfg

# Force mock data BEFORE the app touches any loader.
cfg.DATA_MODE = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402

client = TestClient(app)

# A point safely inside the default Doi Suthep bbox.
INSIDE = {"lat": 18.79, "lon": 98.90}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_area_has_bbox_and_wind():
    r = client.get("/api/area")
    assert r.status_code == 200
    data = r.json()
    assert len(data["bbox"]) == 4
    assert "wind_speed" in data["weather"]
    assert data["grid"]["n_rows"] > 0 and data["grid"]["n_cols"] > 0


def test_risk_returns_overlay_and_indices():
    r = client.get("/api/risk")
    assert r.status_code == 200
    data = r.json()
    assert data["image"].startswith("data:image/png;base64,")
    assert data["danger_class"] in {"Low", "Moderate", "High", "Very High", "Extreme"}
    assert len(data["bounds"]) == 2


def test_simulate_happy_path():
    r = client.post("/api/simulate", json={**INSIDE, "wind_speed": 10, "wind_direction": 225,
                                           "n_runs": 6, "n_steps": 15})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sim_id"]
    assert data["burn_prob_image"].startswith("data:image/png;base64,")
    assert len(data["frames"]) >= 1
    assert 0 <= data["ignition"]["row"] < data["grid"]["n_rows"] if "grid" in data else True
    assert data["wind"]["source"] == "user"
    # ignition cell always ends up burnt
    assert data["stats"]["max_burn_prob"] == 1.0


def test_simulate_defaults_to_live_wind():
    r = client.post("/api/simulate", json={**INSIDE, "n_runs": 4, "n_steps": 8})
    assert r.status_code == 200, r.text
    assert r.json()["wind"]["source"] == "live"


def test_simulate_rejects_point_outside_bbox():
    r = client.post("/api/simulate", json={"lat": 0.0, "lon": 0.0})
    assert r.status_code == 422


def test_simulate_rejects_bad_wind_speed():
    r = client.post("/api/simulate", json={**INSIDE, "wind_speed": 999})
    assert r.status_code == 422


def test_recommend_unknown_sim_is_404():
    r = client.get("/api/recommend", params={"sim_id": "doesnotexist"})
    assert r.status_code == 404


def test_recommend_after_simulate_returns_geojson():
    sim = client.post("/api/simulate", json={
        **INSIDE, "wind_speed": 14, "wind_direction": 270, "fuel_dryness": 0.95,
        "n_runs": 10, "n_steps": 30,
    }).json()
    r = client.get("/api/recommend", params={"sim_id": sim["sim_id"]})
    assert r.status_code == 200, r.text
    gj = r.json()
    assert gj["type"] == "FeatureCollection"
    kinds = {f["properties"]["kind"] for f in gj["features"]}
    assert "fire_head" in kinds and "asset" in kinds
    # Wind FROM the west (270) blows east -> the fire head must be east of (or
    # not west of) the ignition longitude.
    assert gj["summary"]["fire_head"][0] >= INSIDE["lon"] - 0.01


def test_firepoints_shape():
    r = client.get("/api/firepoints")
    assert r.status_code == 200
    assert "enabled" in r.json() and "points" in r.json()
