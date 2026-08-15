"""Renewable-energy analyzer — reproducible pipeline over Eurostat data.

Public entry points:

* :func:`renewable.pipeline.build` — fetch → clean → validate → analyze → write.
* :data:`renewable.config` — all paths, constants and safety limits.
"""
from __future__ import annotations

__version__ = "1.0.0"

from . import config  # noqa: F401  (re-exported for convenience)
