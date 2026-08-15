#!/usr/bin/env python
"""Render a static PNG preview of the dashboard's key findings for the README.

Reads the processed JSON and produces a single, themed figure (EU trend +
forecast, country ranking, sector breakdown). Run after build_data.py:

    python scripts/make_preview.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
from matplotlib import gridspec

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from renewable import config  # noqa: E402

# Palette mirrors the web dashboard.
BRAND = "#1f9d63"
BRAND_D = "#127a4b"
ACCENT = "#0e9488"
DANGER = "#c14b4b"
INK = "#16241c"
MUTED = "#5d6f63"
GRID = "#e2eae2"


def main() -> int:
    data = json.loads(config.PROCESSED_JSON.read_text(encoding="utf-8"))
    eu, fc, target = data["eu"], data["eu"]["forecast"], data["target"]

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.edgecolor": GRID, "axes.linewidth": 1,
        "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED,
        "ytick.color": MUTED, "figure.facecolor": "white", "axes.facecolor": "white",
    })

    fig = plt.figure(figsize=(12, 7.6), dpi=130)
    fig.suptitle("Renewable Energy Analyzer  ·  AB-27 yenilenebilir enerji payı",
                 fontsize=15, fontweight="bold", color=INK, x=0.5, y=0.98)
    gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1.15, 1],
                           hspace=0.42, wspace=0.22,
                           left=0.07, right=0.97, top=0.9, bottom=0.09)

    # ---- Panel 1: EU trend + forecast (spans top row) ---------------------- #
    ax1 = fig.add_subplot(gs[0, :])
    yrs, vals = eu["trend"]["years"], eu["trend"]["values"]
    ax1.plot(yrs, vals, color=BRAND, lw=2.6, marker="o", ms=3, label="Gerçekleşen")
    fyrs = [yrs[-1]] + fc["forecast_years"]
    fvals = [vals[-1]] + fc["forecast_values"]
    flow = [vals[-1]] + fc["forecast_low"]
    fhigh = [vals[-1]] + fc["forecast_high"]
    ax1.plot(fyrs, fvals, color=ACCENT, lw=2.4, ls="--", marker="o", ms=3, label="Tahmin")
    ax1.fill_between(fyrs, flow, fhigh, color=ACCENT, alpha=0.15, label="Tahmin bandı")
    ax1.axhline(target["pct"], color=DANGER, ls=":", lw=1.6)
    ax1.text(yrs[0], target["pct"] + 0.6, f"2030 hedefi %{target['pct']}",
             color=DANGER, fontsize=9, fontweight="bold")
    ax1.set_title(f"Trend ve tahmin  —  {eu['latest']['year']}: %{eu['latest']['value']} "
                  f"(R²={fc['r2']}, naif modeli geçiyor)", fontsize=11, color=INK, loc="left")
    ax1.set_ylabel("Pay (%)")
    ax1.grid(True, color=GRID, lw=0.8)
    ax1.legend(frameon=False, fontsize=9, loc="upper left")
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)

    # ---- Panel 2: Top-15 ranking ------------------------------------------ #
    ax2 = fig.add_subplot(gs[1, 0])
    top = data["ranking"][:15][::-1]
    names = [c["name"] for c in top]
    rv = [c["value"] for c in top]
    ax2.barh(names, rv, color=[(BRAND if i % 2 else BRAND_D) for i in range(len(top))],
             height=0.72)
    ax2.set_title(f"Ülke sıralaması — ilk 15 ({data['meta']['reference_year']})",
                  fontsize=11, color=INK, loc="left")
    ax2.set_xlabel("Pay (%)")
    ax2.tick_params(axis="y", labelsize=8)
    ax2.grid(True, axis="x", color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)

    # ---- Panel 3: Sectors -------------------------------------------------- #
    ax3 = fig.add_subplot(gs[1, 1])
    labtr = {"Overall": "Genel", "Electricity": "Elektrik",
             "Heating & cooling": "Isıtma/soğ.", "Transport": "Ulaşım"}
    secs = eu["sectors"]
    slabs = [labtr.get(s["label"], s["label"]) for s in secs]
    svals = [s["value"] for s in secs]
    bars = ax3.bar(slabs, svals, color=[BRAND, ACCENT, "#c9772a", "#7a86d1"], width=0.62)
    ax3.set_title("Sektöre göre pay (AB-27)", fontsize=11, color=INK, loc="left")
    ax3.set_ylabel("Pay (%)")
    ax3.grid(True, axis="y", color=GRID, lw=0.8)
    for b, v in zip(bars, svals):
        ax3.text(b.get_x() + b.get_width() / 2, v + 0.8, f"%{v}",
                 ha="center", fontsize=8, color=INK, fontweight="bold")
    for s in ("top", "right"):
        ax3.spines[s].set_visible(False)

    fig.text(0.07, 0.02, f"Kaynak: {config.SOURCE_NAME}  ·  {config.SOURCE_LICENSE}",
             fontsize=8, color=MUTED)

    out = ROOT / "docs" / "images" / "dashboard-preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    print(f"[ok] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
