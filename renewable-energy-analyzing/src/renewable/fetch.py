"""Secure downloader for the Eurostat dataset.

Security posture (defence-in-depth for an *outbound* request):

* **HTTPS only** — a plain-HTTP URL is rejected, so the transfer can't be
  silently downgraded or MITM'd.
* **Host allow-list** — only ``ec.europa.eu`` is accepted. This blocks SSRF
  even if the configured URL were ever tampered with (e.g. redirected to an
  internal address).
* **No redirects to other hosts** — redirects are disabled; a moved resource
  is surfaced as an error rather than blindly followed.
* **Bounded** — a connect/read timeout and a streamed byte cap stop a hostile
  or broken endpoint from hanging the process or exhausting memory/disk.
* **Validated** — the payload must look like the expected SDMX-CSV header
  before we trust it, so an error page never gets written as "data".

The function is deliberately dependency-light (``requests`` only) and writes
atomically so a partial download can never clobber a good cached file.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import requests

from . import config

# The first line every valid Eurostat SDMX-CSV response starts with.
_EXPECTED_HEADER_PREFIX = "DATAFLOW,"


class FetchError(RuntimeError):
    """Raised when the download fails validation or a safety limit."""


def _assert_safe_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise FetchError(f"Refusing non-HTTPS URL scheme: {parts.scheme!r}")
    if parts.hostname != config.EUROSTAT_HOST:
        raise FetchError(
            f"Refusing host {parts.hostname!r}; only {config.EUROSTAT_HOST!r} is allowed"
        )


def fetch_raw(
    url: str = config.EUROSTAT_URL,
    dest: Path = config.RAW_CSV,
    *,
    force: bool = False,
) -> Path:
    """Download the Eurostat CSV to ``dest`` and return the path.

    If ``dest`` already exists and ``force`` is False, the cached copy is reused
    (reproducible offline runs). Set ``force=True`` to refresh from the network.
    """
    dest = Path(dest)
    if dest.exists() and not force:
        return dest

    _assert_safe_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": config.USER_AGENT, "Accept": "text/csv"}
    try:
        with requests.get(
            url,
            headers=headers,
            timeout=config.HTTP_TIMEOUT_SECONDS,
            stream=True,
            allow_redirects=False,
        ) as resp:
            if resp.status_code != 200:
                raise FetchError(
                    f"Eurostat returned HTTP {resp.status_code} for dataset "
                    f"{config.EUROSTAT_DATASET!r}"
                )

            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                total += len(chunk)
                if total > config.MAX_DOWNLOAD_BYTES:
                    raise FetchError(
                        f"Download exceeded {config.MAX_DOWNLOAD_BYTES} byte cap; aborting"
                    )
                chunks.append(chunk)
    except requests.Timeout as exc:  # explicit: a timeout is an operational error
        raise FetchError(f"Timed out contacting Eurostat after "
                         f"{config.HTTP_TIMEOUT_SECONDS}s") from exc
    except requests.RequestException as exc:
        raise FetchError(f"Network error contacting Eurostat: {exc}") from exc

    payload = b"".join(chunks)
    text = payload.decode("utf-8-sig", errors="strict")
    if not text.lstrip().startswith(_EXPECTED_HEADER_PREFIX):
        raise FetchError(
            "Downloaded content does not look like Eurostat SDMX-CSV "
            "(unexpected header) — refusing to overwrite cached data"
        )

    # Atomic write: never leave a half-written file where a good one was.
    fd, tmp_name = tempfile.mkstemp(dir=str(dest.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp_name, dest)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)

    return dest
