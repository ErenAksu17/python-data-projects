"""Turn the raw Eurostat SDMX-CSV into one tidy, validated DataFrame.

Raw columns are:
``DATAFLOW, LAST UPDATE, freq, nrg_bal, unit, geo, TIME_PERIOD, OBS_VALUE,
OBS_FLAG, CONF_STATUS``.

We keep only the four energy-balance sectors we analyse, coerce types, drop
missing observations, and attach human-readable labels. The output schema is
the contract the rest of the pipeline (and the tests) rely on.
"""
from __future__ import annotations

import pandas as pd

from . import config

# Output columns — the stable contract downstream code depends on.
TIDY_COLUMNS = [
    "sector_code", "sector", "geo", "geo_name", "iso2",
    "is_eu_aggregate", "year", "value", "flag",
]


def clean(raw_csv=config.RAW_CSV) -> pd.DataFrame:
    """Read the raw CSV and return a tidy, typed, validated long DataFrame."""
    df = pd.read_csv(
        raw_csv,
        usecols=["nrg_bal", "unit", "geo", "TIME_PERIOD", "OBS_VALUE", "OBS_FLAG"],
        dtype={"nrg_bal": "string", "unit": "string", "geo": "string",
               "OBS_FLAG": "string"},
    )

    # Keep only the sectors we model and the percentage unit.
    df = df[df["unit"] == "PC"]
    df = df[df["nrg_bal"].isin(config.SECTORS.keys())].copy()

    # Types: year -> int, value -> float; drop rows with no observation.
    df["year"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["year", "value"]).copy()
    df["year"] = df["year"].astype(int)
    df["value"] = df["value"].astype(float)

    # Human-readable labels.
    df["sector_code"] = df["nrg_bal"]
    df["sector"] = df["sector_code"].map(config.SECTORS)
    df["geo_name"] = df["geo"].map(lambda g: config.GEO_NAMES.get(g, (g, ""))[0])
    df["iso2"] = df["geo"].map(lambda g: config.GEO_NAMES.get(g, (g, ""))[1])
    df["is_eu_aggregate"] = df["geo"] == config.EU_AGGREGATE_GEO
    df["flag"] = df["OBS_FLAG"].fillna("").astype(str)

    tidy = (
        df[TIDY_COLUMNS]
        .sort_values(["sector_code", "geo", "year"])
        .reset_index(drop=True)
    )
    return tidy
