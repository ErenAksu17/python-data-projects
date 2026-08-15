"""An honest forecast — the opposite of "import LinearRegression, multiply by 1.05".

For an annual national renewable-share series we do the simplest thing that is
actually defensible: fit a linear trend on the year, and *prove it earns its
keep* by

1. **Walk-forward validation** — expanding-window, one-step-ahead prediction
   across the most recent years (never a random split: that would leak the
   future into training).
2. **A naive baseline** — "next year equals this year". If the trend model
   can't beat that, we say so instead of pretending it's a forecast.
3. **Reported error** — RMSE, MAE and MAPE on the held-out years, plus R² of
   the final fit and a rough prediction band from the residual spread.

Deliberately *not* used: ARIMA / XGBoost / RandomForest. With ~20 annual points
per country those models overfit; linear trend is the honest choice, and we
document that limitation rather than hide it. See the README "Methods" section.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class ForecastResult:
    method: str
    r2: float
    slope_pct_per_year: float
    holdout_years: list[int]
    model_rmse: float | None
    model_mae: float | None
    model_mape: float | None
    naive_rmse: float | None
    beats_naive: bool | None
    forecast_years: list[int]
    forecast_values: list[float]
    forecast_low: list[float]
    forecast_high: list[float]

    def to_dict(self) -> dict:
        return asdict(self)


def _fit_linear(years: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    """Least-squares line ``value = slope * year + intercept``."""
    slope, intercept = np.polyfit(years, values, deg=1)
    return float(slope), float(intercept)


def _r2(years: np.ndarray, values: np.ndarray, slope: float, intercept: float) -> float:
    pred = slope * years + intercept
    ss_res = float(np.sum((values - pred) ** 2))
    ss_tot = float(np.sum((values - values.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


def _metrics(actual: np.ndarray, pred: np.ndarray) -> tuple[float, float, float]:
    err = actual - pred
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    # MAPE guards against division by zero (shares can be ~0 for late starters).
    nonzero = actual != 0
    mape = float(np.mean(np.abs(err[nonzero] / actual[nonzero])) * 100) if nonzero.any() else float("nan")
    return rmse, mae, mape


def forecast_series(
    years: list[int],
    values: list[float],
    *,
    holdout: int = 4,
    horizon: int = 3,
) -> ForecastResult:
    """Fit, validate and project one annual series."""
    yr = np.asarray(years, dtype=float)
    val = np.asarray(values, dtype=float)
    order = np.argsort(yr)
    yr, val = yr[order], val[order]
    n = len(yr)

    # ---- Walk-forward validation (needs enough history to be meaningful) ---- #
    model_rmse = model_mae = model_mape = naive_rmse = None
    beats_naive = None
    holdout_years: list[int] = []
    usable_holdout = min(holdout, max(0, n - 3))  # keep >=3 points to train on
    if usable_holdout >= 2:
        split = n - usable_holdout
        m_pred, n_pred, actuals = [], [], []
        for i in range(split, n):
            s, b = _fit_linear(yr[:i], val[:i])
            m_pred.append(s * yr[i] + b)
            n_pred.append(val[i - 1])      # naive: previous year's value
            actuals.append(val[i])
        a = np.asarray(actuals)
        model_rmse, model_mae, model_mape = _metrics(a, np.asarray(m_pred))
        naive_rmse, _, _ = _metrics(a, np.asarray(n_pred))
        beats_naive = model_rmse <= naive_rmse
        holdout_years = [int(y) for y in yr[split:]]

    # ---- Final fit on all data + projection -------------------------------- #
    slope, intercept = _fit_linear(yr, val)
    r2 = _r2(yr, val, slope, intercept)
    resid_std = float(np.std(val - (slope * yr + intercept)))

    last_year = int(yr[-1])
    fyears = [last_year + k for k in range(1, horizon + 1)]
    fvals, flow, fhigh = [], [], []
    for fy in fyears:
        point = slope * fy + intercept
        # Simple, honest band: point ± ~1.96 residual sigma, clamped to >=0.
        band = 1.96 * resid_std
        fvals.append(round(point, 2))
        flow.append(round(max(0.0, point - band), 2))
        fhigh.append(round(point + band, 2))

    return ForecastResult(
        method="Linear trend (OLS on year), walk-forward validated",
        r2=round(r2, 4),
        slope_pct_per_year=round(slope, 4),
        holdout_years=holdout_years,
        model_rmse=None if model_rmse is None else round(model_rmse, 3),
        model_mae=None if model_mae is None else round(model_mae, 3),
        model_mape=None if model_mape is None else round(model_mape, 2),
        naive_rmse=None if naive_rmse is None else round(naive_rmse, 3),
        beats_naive=beats_naive,
        forecast_years=fyears,
        forecast_values=fvals,
        forecast_low=flow,
        forecast_high=fhigh,
    )
