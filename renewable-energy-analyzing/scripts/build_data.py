#!/usr/bin/env python
"""CLI: build the processed dataset.

Usage
-----
    python scripts/build_data.py            # use cached raw data if present
    python scripts/build_data.py --refresh  # re-download from Eurostat

Run from the repository root.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ``src`` importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from renewable import config  # noqa: E402
from renewable.pipeline import build  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build renewable-energy dataset")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-download from Eurostat instead of using cached raw data")
    args = parser.parse_args()

    payload = build(refresh=args.refresh)
    eu = payload["eu"]
    print(f"[ok] wrote {config.PROCESSED_JSON}")
    print(f"     EU {eu['latest']['year']}: {eu['latest']['value']}%  "
          f"(gap to {payload['target']['year']} target {payload['target']['pct']}%: {eu['gap_to_target']} pp)")
    print(f"     countries analysed: {len(payload['countries'])}  "
          f"| RES-E>100% cases: {len(payload['insights']['res_e_over_100'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
