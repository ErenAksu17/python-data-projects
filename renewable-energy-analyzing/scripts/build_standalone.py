#!/usr/bin/env python
"""Assemble a single self-contained HTML dashboard (no server, no network).

Inlines the CSS, the processed data, Chart.js and the app logic into one file,
swapping the API's `fetch` calls for reads from the embedded data. Useful as a
shareable live demo. Run after build_data.py:

    python scripts/build_standalone.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from renewable import config  # noqa: E402

WEB = ROOT / "web"


def _body_inner(html: str) -> str:
    inner = html.split("<body>", 1)[1].split("</body>", 1)[0]
    # Drop the external <script src=...> tags; we inline everything instead.
    return "\n".join(l for l in inner.splitlines() if "<script src=" not in l)


# Replace the network api() with one that reads the embedded dataset.
_API_OLD = '''async function api(path) {
  const res = await fetch(path, { headers: { "Accept": "application/json" } });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json();
}'''

_API_NEW = '''async function api(path) {
  const D = window.__DATA__;
  if (path === "/api/summary") return { meta: D.meta, target: D.target, eu: D.eu, insights: D.insights };
  if (path.startsWith("/api/ranking")) {
    const q = path.split("?")[1] || "";
    const m = /limit=(\\d+)/.exec(q); const lim = m ? +m[1] : 37;
    return { reference_year: D.meta.reference_year, ranking: D.ranking.slice(0, lim) };
  }
  if (path.startsWith("/api/country/")) {
    const geo = decodeURIComponent(path.split("/").pop());
    const c = (D.countries || []).find((x) => x.geo === geo);
    if (!c) throw new Error("404");
    return c;
  }
  throw new Error("unknown path " + path);
}'''


def main() -> int:
    css = (WEB / "static" / "styles.css").read_text(encoding="utf-8")
    chartjs = (WEB / "static" / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8")
    app = (WEB / "static" / "app.js").read_text(encoding="utf-8")
    body = _body_inner((WEB / "index.html").read_text(encoding="utf-8"))
    data = json.loads(config.PROCESSED_JSON.read_text(encoding="utf-8"))

    if _API_OLD not in app:
        raise SystemExit("api() block not found in app.js — update the template")
    app = app.replace(_API_OLD, _API_NEW)
    # Run immediately if the document already parsed (artifacts run late).
    app = app.replace(
        'document.addEventListener("DOMContentLoaded", main);',
        'if (document.readyState === "loading") '
        'document.addEventListener("DOMContentLoaded", main); else main();',
    )

    data_js = json.dumps(data, ensure_ascii=False)
    out = "\n".join([
        "<title>Renewable Energy Analyzer</title>",
        f"<style>\n{css}\n</style>",
        body,
        f"<script>window.__DATA__ = {data_js};</script>",
        f"<script>{chartjs}</script>",
        f"<script>\n{app}\n</script>",
    ])

    dest = ROOT / "docs" / "standalone.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    print(f"[ok] wrote {dest} ({len(out)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
