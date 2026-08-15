"""Cleaning, validation and analysis over the real raw snapshot."""
from __future__ import annotations

import pandas as pd
import pytest

from renewable import config
from renewable.analyze import analyze
from renewable.clean import TIDY_COLUMNS, clean
from renewable.validate import DataValidationError, validate


@pytest.fixture(scope="module")
def tidy() -> pd.DataFrame:
    return clean()


def test_clean_schema(tidy):
    assert list(tidy.columns) == TIDY_COLUMNS
    assert not tidy.empty


def test_clean_types(tidy):
    assert tidy["year"].dtype.kind in "iu"
    assert tidy["value"].dtype.kind == "f"
    assert tidy["year"].notna().all()
    assert tidy["value"].notna().all()


def test_only_known_sectors(tidy):
    assert set(tidy["sector_code"].unique()) <= set(config.SECTORS)


def test_overall_share_in_range(tidy):
    overall = tidy[tidy["sector_code"] == config.OVERALL_SECTOR]
    assert overall["value"].between(0, 100).all()


def test_electricity_may_exceed_100(tidy):
    """The signature insight: RES-E can legitimately exceed 100%."""
    elc = tidy[tidy["sector_code"] == "REN_ELC"]
    assert (elc["value"] > 100).any()


def test_validate_passes_on_clean(tidy):
    assert validate(tidy) is tidy


def test_validate_rejects_out_of_range_overall(tidy):
    bad = tidy.copy()
    mask = bad["sector_code"] == config.OVERALL_SECTOR
    idx = bad[mask].index[0]
    bad.loc[idx, "value"] = 150.0  # impossible overall share
    with pytest.raises(DataValidationError):
        validate(bad)


def test_validate_rejects_duplicates(tidy):
    bad = pd.concat([tidy, tidy.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError):
        validate(bad)


def test_analyze_contract(tidy):
    out = analyze(tidy)
    for key in ("meta", "target", "eu", "countries", "ranking", "insights"):
        assert key in out
    assert 0 <= out["eu"]["latest"]["value"] <= 100
    # Ranking is sorted descending by value.
    vals = [r["value"] for r in out["ranking"]]
    assert vals == sorted(vals, reverse=True)
    # The RES-E>100 insight is populated from real data.
    assert len(out["insights"]["res_e_over_100"]) >= 1
