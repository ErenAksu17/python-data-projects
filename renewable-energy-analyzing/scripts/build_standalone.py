#!/usr/bin/env python
"""Turn the built React app into self-contained, data-embedded HTML.

Vite (with vite-plugin-singlefile) already inlines all JS/CSS into
frontend/dist/index.html. Here we inject the processed dataset as
`window.__DATA__` so the dashboard runs with no server and no network — as a
double-clickable offline file and as a Claude artifact.

Run after `npm run build` (in frontend/) and `build_data.py`:

    python scripts/build_standalone.py

Outputs:
    docs/standalone.html  — full HTML document (offline, double-click)
    docs/artifact.html    — head/body inner only, for publishing as an artifact
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from renewable import config  # noqa: E402

# The inlined single-file build (npm run build:standalone → dist-single/).
DIST = ROOT / "frontend" / "dist-single" / "index.html"


def main() -> int:
    if not DIST.exists():
        raise SystemExit(
            f"Build missing: {DIST}. Run `npm run build:standalone` in frontend/ first."
        )

    html = DIST.read_text(encoding="utf-8")
    data = json.loads(config.PROCESSED_JSON.read_text(encoding="utf-8"))
    data_script = (
        "<script>window.__DATA__ = "
        + json.dumps(data, ensure_ascii=False)
        + ";</script>"
    )

    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    # 1) Full offline document: inject the data right after <head>.
    full = html.replace("<head>", "<head>\n" + data_script, 1)
    (docs / "standalone.html").write_text(full, encoding="utf-8")

    # 2) Artifact fragment: strip the document wrappers the artifact host adds
    #    back itself, drop the title (passed as a param), prepend the data.
    frag = html
    frag = re.sub(r"<!doctype[^>]*>", "", frag, flags=re.I)
    frag = re.sub(r"</?html[^>]*>", "", frag, flags=re.I)
    frag = re.sub(r"</?head[^>]*>", "", frag, flags=re.I)
    frag = re.sub(r"<body[^>]*>", "", frag, flags=re.I)
    frag = frag.replace("</body>", "")
    frag = re.sub(r"<title>.*?</title>", "", frag, flags=re.I | re.S)
    frag = re.sub(r'<meta charset[^>]*>', "", frag, flags=re.I)
    artifact = (
        "<title>Renewable Energy Analyzer</title>\n" + data_script + "\n" + frag.strip()
    )
    (docs / "artifact.html").write_text(artifact, encoding="utf-8")

    print(f"[ok] wrote {docs / 'standalone.html'} ({len(full)//1024} KB)")
    print(f"[ok] wrote {docs / 'artifact.html'} ({len(artifact)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
