"""The forecast must be real, validated, and honest about uncertainty."""
from __future__ import annotations

import math

from renewable.forecast import forecast_series


def test_upward_trend_recovered():
    years = list(range(2004, 2024))
    values = [10 + 0.8 * (y - 2004) for y in years]  # perfectly linear, +0.8/yr
    r = forecast_series(years, values, holdout=4, horizon=3)
    assert r.slope_pct_per_year == 0.8 or abs(r.slope_pct_per_year - 0.8) < 1e-6
    assert r.r2 > 0.999


def test_forecast_contract():
    years = list(range(2004, 2024))
    values = [10 + 0.8 * (y - 2004) for y in years]
    r = forecast_series(years, values, holdout=4, horizon=3)
    assert len(r.forecast_years) == 3
    assert len(r.forecast_values) == 3
    assert r.forecast_years[0] == 2024
    # Values finite and bands ordered low <= point <= high.
    for lo, pt, hi in zip(r.forecast_low, r.forecast_values, r.forecast_high):
        assert all(math.isfinite(x) for x in (lo, pt, hi))
        assert lo <= pt <= hi


def test_beats_naive_on_trending_data():
    years = list(range(2004, 2024))
    values = [10 + 0.8 * (y - 2004) for y in years]
    r = forecast_series(years, values, holdout=4, horizon=3)
    assert r.beats_naive is True
    assert r.model_rmse is not None and r.naive_rmse is not None
    assert r.model_rmse <= r.naive_rmse


def test_forecast_low_never_negative():
    years = list(range(2010, 2024))
    values = [1.0 for _ in years]  # flat, tiny values
    r = forecast_series(years, values, holdout=3, horizon=3)
    assert all(lo >= 0 for lo in r.forecast_low)
