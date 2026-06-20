"""
risk_ml.py - Inference for the ML fire-susceptibility model.

Loads the trained scikit-learn model (saved by scripts/train_risk_model.py) and
predicts a 0-1 susceptibility grid for the app's bbox. If no model has been
trained yet, callers get a clear error and the rest of the app (FWI risk, CA
spread) keeps working.
"""

from __future__ import annotations

import numpy as np

from backend import config
from backend.data.grid import Grid
from backend.ml.features import feature_stack

MODEL_PATH = config.CACHE_DIR / "risk_model.joblib"


def model_available() -> bool:
    return MODEL_PATH.exists()


def load_model() -> dict:
    import joblib

    return joblib.load(MODEL_PATH)  # {"model", "feature_names", "metrics"}


def predict_risk_grid(grid: Grid, *, terrain=None, fuel=None, bundle=None) -> dict:
    """Predict per-cell fire susceptibility (0-1) over the grid.

    Pass a `bundle` to skip disk loading (used by tests). Non-flammable cells are
    forced to 0 so water/built-up never light up.
    """
    if bundle is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                "ML model not trained yet — run scripts/train_risk_model.py (needs FIRMS_API_KEY)"
            )
        bundle = load_model()

    from backend.data import fuel as fuel_mod
    from backend.data import terrain as terrain_mod

    terrain = terrain or terrain_mod.get_terrain(grid)
    fuel = fuel or fuel_mod.get_fuel(grid)

    stack, names = feature_stack(grid, terrain, fuel)
    h, w, f = stack.shape
    proba = bundle["model"].predict_proba(stack.reshape(-1, f))[:, 1].reshape(h, w)
    proba = np.clip(proba, 0.0, 1.0)
    proba[fuel["nonflammable"]] = 0.0
    return {"risk": proba, "metrics": bundle.get("metrics", {}), "feature_names": names}
