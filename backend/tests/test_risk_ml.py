"""Tests for the ML fire-susceptibility layer.

Runs in DATA_MODE=mock and trains a tiny model in-test (no network, no FIRMS
key) so it verifies the feature builder + inference contract without needing the
real trained model on disk.
"""

import numpy as np

import backend.config as cfg

cfg.DATA_MODE = "mock"

from backend.config import GRID_COLS, GRID_ROWS  # noqa: E402
from backend.data import fuel as fuel_mod  # noqa: E402
from backend.data import terrain as terrain_mod  # noqa: E402
from backend.data.grid import Grid  # noqa: E402
from backend.ml.features import FEATURE_NAMES, feature_stack  # noqa: E402
from backend.models.risk_ml import predict_risk_grid  # noqa: E402


def _tiny_bundle():
    from sklearn.ensemble import GradientBoostingClassifier

    grid = Grid.from_config()
    terr = terrain_mod.get_terrain(grid)
    fu = fuel_mod.get_fuel(grid)
    stack, names = feature_stack(grid, terr, fu)
    X = stack.reshape(-1, stack.shape[-1])
    # synthetic target: more fuel + steeper slope -> more fire-prone (just to fit)
    score = stack[..., 4].ravel() * 2 + stack[..., 1].ravel() / 30.0
    y = (score > np.median(score)).astype(int)
    model = GradientBoostingClassifier(random_state=0, n_estimators=20).fit(X, y)
    return grid, terr, fu, {"model": model, "feature_names": names, "metrics": {"auc": 0.9}}


def test_feature_stack_shape():
    grid = Grid.from_config()
    stack, names = feature_stack(grid, terrain_mod.get_terrain(grid), fuel_mod.get_fuel(grid))
    assert stack.shape == (GRID_ROWS, GRID_COLS, len(FEATURE_NAMES))
    assert names == FEATURE_NAMES
    assert np.isfinite(stack).all()


def test_predict_grid_wellformed_and_respects_nonflammable():
    grid, terr, fu, bundle = _tiny_bundle()
    out = predict_risk_grid(grid, terrain=terr, fuel=fu, bundle=bundle)
    risk = out["risk"]
    assert risk.shape == (GRID_ROWS, GRID_COLS)
    assert np.isfinite(risk).all()
    assert risk.min() >= 0.0 and risk.max() <= 1.0
    assert np.all(risk[fu["nonflammable"]] == 0.0)
