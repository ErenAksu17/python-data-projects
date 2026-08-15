"""Central configuration — single source of truth, zero secrets.

Every tunable (paths, the upstream data source, network safety limits, domain
constants) lives here so the rest of the code never hard-codes a value. Nothing
in this module is sensitive: the Eurostat dissemination API is public and
key-less. Real secrets (were any ever needed) belong in a local ``.env`` file
that is git-ignored and read via :func:`get_env`.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths (all relative to the repository root — never an absolute user path)     #
# --------------------------------------------------------------------------- #
ROOT_DIR: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"

RAW_CSV: Path = RAW_DIR / "eurostat_nrg_ind_ren.csv"
PROCESSED_JSON: Path = PROCESSED_DIR / "renewable.json"

# --------------------------------------------------------------------------- #
# Upstream data source — Eurostat, dataset nrg_ind_ren (share of renewables)    #
# --------------------------------------------------------------------------- #
EUROSTAT_HOST: str = "ec.europa.eu"  # allow-list: fetch refuses any other host
EUROSTAT_DATASET: str = "nrg_ind_ren"
EUROSTAT_URL: str = (
    "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
    f"{EUROSTAT_DATASET}/?format=SDMX-CSV&startPeriod=2004"
)
# Provenance shown to users / stored in output.
SOURCE_NAME: str = "Eurostat — nrg_ind_ren (Share of energy from renewable sources)"
SOURCE_URL: str = "https://ec.europa.eu/eurostat/databrowser/view/nrg_ind_ren"
SOURCE_LICENSE: str = "Eurostat open data (CC BY 4.0)"

# --------------------------------------------------------------------------- #
# Network safety limits (defence-in-depth for the outbound fetch)               #
# --------------------------------------------------------------------------- #
HTTP_TIMEOUT_SECONDS: float = 60.0
MAX_DOWNLOAD_BYTES: int = 8 * 1024 * 1024  # 8 MB hard cap — the file is ~230 KB
USER_AGENT: str = "renewable-energy-analyzer/1.0 (+https://github.com/ErenAksu17)"

# --------------------------------------------------------------------------- #
# Domain constants                                                              #
# --------------------------------------------------------------------------- #
# Eurostat energy-balance codes we care about, mapped to human labels.
SECTORS: dict[str, str] = {
    "REN": "Overall",
    "REN_ELC": "Electricity",
    "REN_HEAT_CL": "Heating & cooling",
    "REN_TRA": "Transport",
}
OVERALL_SECTOR: str = "REN"

# The EU-27 aggregate row (post-2020 composition) — kept separate from countries.
EU_AGGREGATE_GEO: str = "EU27_2020"

# EU Renewable Energy Directive (EU/2023/2413): binding 2030 target.
EU_2030_TARGET_PCT: float = 42.5
TARGET_YEAR: int = 2030

# How many recent years to hold out when validating the forecast.
FORECAST_HOLDOUT_YEARS: int = 4
# How many years ahead the headline forecast projects.
FORECAST_HORIZON_YEARS: int = 3

# Eurostat geo code -> (English name, ISO alpha-2 for flag rendering).
# EL=Greece (ISO GR), XK=Kosovo (no ISO flag), EU aggregate handled separately.
GEO_NAMES: dict[str, tuple[str, str]] = {
    "AL": ("Albania", "AL"), "AT": ("Austria", "AT"),
    "BA": ("Bosnia & Herzegovina", "BA"), "BE": ("Belgium", "BE"),
    "BG": ("Bulgaria", "BG"), "CY": ("Cyprus", "CY"), "CZ": ("Czechia", "CZ"),
    "DE": ("Germany", "DE"), "DK": ("Denmark", "DK"), "EE": ("Estonia", "EE"),
    "EL": ("Greece", "GR"), "ES": ("Spain", "ES"), "FI": ("Finland", "FI"),
    "FR": ("France", "FR"), "GE": ("Georgia", "GE"), "HR": ("Croatia", "HR"),
    "HU": ("Hungary", "HU"), "IE": ("Ireland", "IE"), "IS": ("Iceland", "IS"),
    "IT": ("Italy", "IT"), "LT": ("Lithuania", "LT"), "LU": ("Luxembourg", "LU"),
    "LV": ("Latvia", "LV"), "MD": ("Moldova", "MD"), "ME": ("Montenegro", "ME"),
    "MK": ("North Macedonia", "MK"), "MT": ("Malta", "MT"),
    "NL": ("Netherlands", "NL"), "NO": ("Norway", "NO"), "PL": ("Poland", "PL"),
    "PT": ("Portugal", "PT"), "RO": ("Romania", "RO"), "RS": ("Serbia", "RS"),
    "SE": ("Sweden", "SE"), "SI": ("Slovenia", "SI"), "SK": ("Slovakia", "SK"),
    "XK": ("Kosovo", "XK"),
    "EU27_2020": ("European Union (27)", "EU"),
}


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a configuration value from the environment (optionally via .env).

    Kept as the single access point for environment-driven settings so secrets
    never get scattered as ``os.environ[...]`` calls across the codebase.
    """
    return os.environ.get(name, default)
