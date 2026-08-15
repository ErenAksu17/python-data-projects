"""End-to-end orchestration: fetch → clean → validate → analyze → write JSON."""
from __future__ import annotations

import json
from pathlib import Path

from . import config
from .analyze import analyze
from .clean import clean
from .fetch import fetch_raw
from .validate import validate


def build(*, refresh: bool = False, out: Path = config.PROCESSED_JSON) -> dict:
    """Run the full pipeline and write the processed payload to ``out``.

    Parameters
    ----------
    refresh:
        When True, re-download from Eurostat even if a cached raw file exists.
    out:
        Destination for the processed JSON the API/dashboard consume.
    """
    fetch_raw(force=refresh)
    tidy = clean()
    validate(tidy)
    payload = analyze(tidy)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
