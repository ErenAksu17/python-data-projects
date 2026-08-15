"""Compute every headline metric and assemble the processed JSON payload.

This is the analytical heart: from the tidy frame it derives the EU trend and
gap-to-target, the country ranking, per-country CAGR and trend series, the EU
sector breakdown, the RES-E>100% signature insight, and the validated EU
forecast. The returned dict is exactly what the API serves and the dashboard
renders — one well-defined contract.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from . import config
from .forecast import forecast_series


def _trend(sub: pd.DataFrame) -> dict:
    sub = sub.sort_values("year")
    return {"years": sub["year"].tolist(), "values": [round(v, 3) for v in sub["value"]]}


def _cagr(sub: pd.DataFrame) -> float | None:
    """Compound annual growth rate (%) across the available window."""
    sub = sub.sort_values("year")
    if len(sub) < 2:
        return None
    first, last = float(sub["value"].iloc[0]), float(sub["value"].iloc[-1])
    span = int(sub["year"].iloc[-1] - sub["year"].iloc[0])
    if first <= 0 or span <= 0:
        return None
    return round(((last / first) ** (1 / span) - 1) * 100, 2)


def _reference_year(overall_countries: pd.DataFrame) -> int:
    """Latest year with near-complete country coverage — for a fair ranking.

    We avoid the very newest year when it is only partially reported (e.g. a
    provisional year that many countries haven't filed yet), because ranking on
    it would silently drop the countries that are missing. So we take the most
    recent year whose coverage is within 90% of the best-covered year.
    """
    counts = overall_countries.groupby("year")["geo"].nunique()
    if counts.empty:
        return int(overall_countries["year"].max())
    threshold = counts.max() * 0.9
    eligible = counts[counts >= threshold]
    return int(eligible.index.max())


def analyze(df: pd.DataFrame) -> dict:
    overall = df[df["sector_code"] == config.OVERALL_SECTOR]
    eu_overall = overall[overall["geo"] == config.EU_AGGREGATE_GEO]
    countries_overall = overall[~overall["is_eu_aggregate"]]

    # ---- EU headline + trend + forecast ------------------------------------ #
    eu_trend = _trend(eu_overall)
    eu_latest_row = eu_overall.sort_values("year").iloc[-1]
    # Eurostat flags provisional/estimated observations with 'p'/'e'.
    latest_flag = str(eu_latest_row["flag"])
    eu_latest = {
        "year": int(eu_latest_row["year"]),
        "value": round(float(eu_latest_row["value"]), 2),
        "provisional": ("p" in latest_flag) or ("e" in latest_flag),
    }
    gap = round(config.EU_2030_TARGET_PCT - eu_latest["value"], 2)

    eu_fc = forecast_series(
        eu_trend["years"], eu_trend["values"],
        holdout=config.FORECAST_HOLDOUT_YEARS,
        horizon=config.FORECAST_HORIZON_YEARS,
    ).to_dict()

    # ---- EU sector breakdown (each sector's own latest year) --------------- #
    sectors = []
    for code, label in config.SECTORS.items():
        sec = df[(df["sector_code"] == code) & (df["geo"] == config.EU_AGGREGATE_GEO)]
        if sec.empty:
            continue
        row = sec.sort_values("year").iloc[-1]
        sectors.append({"code": code, "label": label,
                        "value": round(float(row["value"]), 2), "year": int(row["year"])})

    # ---- Per-country: latest value, CAGR, full trend ----------------------- #
    ref_year = _reference_year(countries_overall)
    countries = []
    for geo, sub in countries_overall.groupby("geo"):
        latest = sub.sort_values("year").iloc[-1]
        name, iso2 = config.GEO_NAMES.get(geo, (geo, ""))
        ref = sub[sub["year"] == ref_year]
        countries.append({
            "geo": geo, "name": name, "iso2": iso2,
            "latest_year": int(latest["year"]),
            "latest_value": round(float(latest["value"]), 2),
            "ref_value": round(float(ref["value"].iloc[0]), 2) if not ref.empty else None,
            "cagr": _cagr(sub),
            "trend": _trend(sub),
        })
    countries.sort(key=lambda c: c["latest_value"], reverse=True)

    # Ranking at a single reference year (fair, like-for-like comparison).
    ranking = sorted(
        [c for c in countries if c["ref_value"] is not None],
        key=lambda c: c["ref_value"], reverse=True,
    )
    for i, c in enumerate(ranking, start=1):
        c_rank = {"rank": i}
        c.update(c_rank)

    # ---- Signature insight: electricity share > 100% (hydro net-exporters) - #
    elc = df[df["sector_code"] == "REN_ELC"]
    res_e_over_100 = []
    for geo, sub in elc.groupby("geo"):
        row = sub.sort_values("year").iloc[-1]
        if float(row["value"]) > 100:
            name, iso2 = config.GEO_NAMES.get(geo, (geo, ""))
            res_e_over_100.append({"geo": geo, "name": name, "iso2": iso2,
                                   "value": round(float(row["value"]), 2),
                                   "year": int(row["year"])})
    res_e_over_100.sort(key=lambda x: x["value"], reverse=True)

    return {
        "meta": {
            "source": config.SOURCE_NAME,
            "source_url": config.SOURCE_URL,
            "license": config.SOURCE_LICENSE,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reference_year": ref_year,
        },
        "target": {"pct": config.EU_2030_TARGET_PCT, "year": config.TARGET_YEAR},
        "eu": {
            "geo": config.EU_AGGREGATE_GEO,
            "name": config.GEO_NAMES[config.EU_AGGREGATE_GEO][0],
            "latest": eu_latest,
            "gap_to_target": gap,
            "trend": eu_trend,
            "sectors": sectors,
            "forecast": eu_fc,
        },
        "countries": countries,
        "ranking": [
            {"rank": c["rank"], "geo": c["geo"], "name": c["name"],
             "iso2": c["iso2"], "value": c["ref_value"]}
            for c in ranking
        ],
        "insights": {
            "res_e_over_100": res_e_over_100,
            "reference_year": ref_year,
        },
    }
