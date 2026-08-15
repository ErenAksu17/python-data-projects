"""Fail-loud data validation, run right after cleaning.

Treating data as untrusted input — even from an official source — is what keeps
a silent upstream change (a renamed column, an out-of-range value, a duplicated
row) from quietly corrupting every chart downstream. Each check raises with a
precise message so a failure points straight at the problem.
"""
from __future__ import annotations

import pandas as pd

from . import config
from .clean import TIDY_COLUMNS


class DataValidationError(RuntimeError):
    """Raised when the cleaned dataset violates an expected invariant."""


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Assert every invariant the pipeline relies on; return ``df`` unchanged."""
    # 1. Schema: exactly the columns we promised, in order.
    if list(df.columns) != TIDY_COLUMNS:
        raise DataValidationError(
            f"Unexpected columns.\n  expected={TIDY_COLUMNS}\n  got={list(df.columns)}"
        )

    # 2. Non-empty.
    if df.empty:
        raise DataValidationError("Cleaned dataset is empty")

    # 3. No missing keys or values.
    for col in ("sector_code", "geo", "year", "value"):
        if df[col].isna().any():
            raise DataValidationError(f"Column {col!r} contains missing values")

    # 4. Overall renewable share is a percentage and must sit in [0, 100].
    #    (Sector shares such as electricity may legitimately exceed 100% for
    #    hydro net-exporters, so the ceiling is only enforced on REN.)
    overall = df[df["sector_code"] == config.OVERALL_SECTOR]
    bad = overall[(overall["value"] < 0) | (overall["value"] > 100)]
    if not bad.empty:
        sample = bad[["geo", "year", "value"]].head(5).to_dict("records")
        raise DataValidationError(
            f"Overall renewable share outside [0, 100]: {sample}"
        )

    # 5. No negative percentages anywhere.
    if (df["value"] < 0).any():
        raise DataValidationError("Negative percentage values found")

    # 6. Sector codes are all known.
    unknown = set(df["sector_code"].unique()) - set(config.SECTORS)
    if unknown:
        raise DataValidationError(f"Unknown sector codes: {sorted(unknown)}")

    # 7. No duplicate (sector, geo, year) observations.
    dupes = df.duplicated(subset=["sector_code", "geo", "year"])
    if dupes.any():
        raise DataValidationError(f"{int(dupes.sum())} duplicate (sector, geo, year) rows")

    # 8. The EU aggregate must be present (headline numbers depend on it).
    if not (df["geo"] == config.EU_AGGREGATE_GEO).any():
        raise DataValidationError(
            f"EU aggregate {config.EU_AGGREGATE_GEO!r} missing from dataset"
        )

    return df
