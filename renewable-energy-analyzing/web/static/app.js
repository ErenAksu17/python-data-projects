/* Dashboard logic. Talks only to the same-origin API, renders with the
   locally-vendored Chart.js. No inline handlers, no external calls — CSP clean. */
"use strict";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const fmt = (n, d = 1) => (n === null || n === undefined || Number.isNaN(n)) ? "—" : Number(n).toFixed(d);

async function api(path) {
  const res = await fetch(path, { headers: { "Accept": "application/json" } });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json();
}

/* ---- Chart.js theme defaults ------------------------------------------- */
function applyChartTheme() {
  if (!window.Chart) return;
  Chart.defaults.font.family = css("--font") ||
    "-apple-system, Segoe UI, Roboto, sans-serif";
  Chart.defaults.color = css("--text-muted");
  Chart.defaults.borderColor = css("--border");
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
}

const charts = {};
function draw(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
  return charts[id];
}

/* ---- KPI cards --------------------------------------------------------- */
function renderKpis(data) {
  const eu = data.eu, target = data.target;
  const leader = data.ranking_top || null;
  const grid = document.getElementById("kpi-grid");
  const prov = eu.latest.provisional ? "*" : "";
  grid.innerHTML = `
    <div class="kpi-card accent">
      <div class="kpi-label">AB-27 yenilenebilir payı (${eu.latest.year}${prov})</div>
      <div class="kpi-value">${fmt(eu.latest.value)}<span class="unit">%</span></div>
      <div class="kpi-sub">${prov ? "*geçici (provisional) veri" : "kesinleşmiş veri"}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">2030 hedefine kalan</div>
      <div class="kpi-value">${fmt(eu.gap_to_target)}<span class="unit">puan</span></div>
      <div class="kpi-sub">yıllık +${fmt(eu.forecast.slope_pct_per_year, 2)} puan hızla</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">2030 AB hedefi</div>
      <div class="kpi-value">${fmt(target.pct)}<span class="unit">%</span></div>
      <div class="kpi-sub">RED direktifi (EU/2023/2413)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Lider ülke (${data.reference_year})</div>
      <div class="kpi-value" style="font-size:1.5rem">${leader ? leader.name : "—"}</div>
      <div class="kpi-sub">${leader ? fmt(leader.value) + "%" : ""}</div>
    </div>`;
}

/* ---- Progress to target ------------------------------------------------ */
function renderProgress(data) {
  const eu = data.eu, target = data.target;
  const pct = Math.min(100, (eu.latest.value / target.pct) * 100);
  document.getElementById("progress-fill").style.width = pct.toFixed(1) + "%";
  const t = document.getElementById("progress-target");
  t.style.left = "100%";
  document.getElementById("progress-caption").textContent =
    `AB-27, ${target.year} hedefinin (%${fmt(target.pct)}) %${pct.toFixed(0)}'ini tamamladı. ` +
    `${eu.latest.year} itibarıyla pay %${fmt(eu.latest.value)}.`;
}

/* ---- Trend + forecast -------------------------------------------------- */
function renderTrend(data) {
  const eu = data.eu, fc = eu.forecast;
  const histYears = eu.trend.years, histVals = eu.trend.values;
  const lastIdx = histYears.length - 1;
  const labels = histYears.concat(fc.forecast_years);

  const line = new Array(labels.length).fill(null);
  const high = new Array(labels.length).fill(null);
  const low = new Array(labels.length).fill(null);
  // Anchor the forecast + band to the last actual point for visual continuity.
  line[lastIdx] = histVals[lastIdx];
  high[lastIdx] = histVals[lastIdx];
  low[lastIdx] = histVals[lastIdx];
  fc.forecast_years.forEach((_, k) => {
    const i = histYears.length + k;
    line[i] = fc.forecast_values[k];
    high[i] = fc.forecast_high[k];
    low[i] = fc.forecast_low[k];
  });

  const brand = css("--brand"), accent = css("--accent");
  const target = data.target;

  document.getElementById("forecast-note").textContent =
    `Yöntem: ${fc.method}. R²=${fc.r2}, holdout MAPE=${fmt(fc.model_mape, 1)}%, ` +
    `naif modeli ${fc.beats_naive ? "geçiyor ✓" : "geçemiyor"}.`;

  draw("trendChart", {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Tahmin bandı", data: high, borderColor: "transparent",
          backgroundColor: hexA(accent, .14), pointRadius: 0, fill: "+1" },
        { label: "_low", data: low, borderColor: "transparent",
          backgroundColor: "transparent", pointRadius: 0, fill: false },
        { label: "Gerçekleşen", data: histVals.concat(new Array(fc.forecast_years.length).fill(null)),
          borderColor: brand, backgroundColor: hexA(brand, .08),
          borderWidth: 2.5, tension: .25, pointRadius: 2, fill: true },
        { label: "Tahmin", data: line, borderColor: accent, borderDash: [6, 4],
          borderWidth: 2.5, tension: .2, pointRadius: 3, fill: false },
      ],
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { filter: (i) => i.text !== "_low" && i.text !== "Tahmin bandı" } },
        tooltip: { callbacks: { label: (c) => c.dataset.label.startsWith("_") ? null :
          `${c.dataset.label}: ${fmt(c.parsed.y)}%` } },
        annotation: undefined,
      },
      scales: {
        y: { title: { display: true, text: "Pay (%)" }, suggestedMax: target.pct + 4,
             grid: { color: hexA(css("--text-muted"), .12) } },
        x: { grid: { display: false } },
      },
    },
  });
}

/* ---- Ranking (top 15) -------------------------------------------------- */
function renderRanking(data, ranking) {
  document.getElementById("ranking-year").textContent = `(${ranking.reference_year})`;
  const top = ranking.ranking.slice(0, 15);
  const brand = css("--brand");
  draw("rankingChart", {
    type: "bar",
    data: {
      labels: top.map((c) => c.name),
      datasets: [{
        label: "Yenilenebilir payı (%)",
        data: top.map((c) => c.value),
        backgroundColor: top.map((_, i) => hexA(brand, 1 - i * 0.035)),
        borderRadius: 5,
      }],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => ` ${fmt(c.parsed.x)}%` } } },
      scales: {
        x: { grid: { color: hexA(css("--text-muted"), .12) }, ticks: { callback: (v) => v + "%" } },
        y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: 11 } } },
      },
    },
  });
}

/* ---- Sector breakdown -------------------------------------------------- */
function renderSectors(data) {
  const sectors = data.eu.sectors;
  const labelTr = { "Overall": "Genel", "Electricity": "Elektrik",
                    "Heating & cooling": "Isıtma/soğutma", "Transport": "Ulaşım" };
  const colors = [css("--brand"), css("--accent"), css("--warn"), "#7a86d1"];
  draw("sectorChart", {
    type: "bar",
    data: {
      labels: sectors.map((s) => labelTr[s.label] || s.label),
      datasets: [{
        label: "Pay (%)",
        data: sectors.map((s) => s.value),
        backgroundColor: sectors.map((_, i) => colors[i % colors.length]),
        borderRadius: 6,
      }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => ` ${fmt(c.parsed.y)}%` } } },
      scales: {
        y: { grid: { color: hexA(css("--text-muted"), .12) }, ticks: { callback: (v) => v + "%" }, beginAtZero: true },
        x: { grid: { display: false } },
      },
    },
  });
}

/* ---- Signature insight ------------------------------------------------- */
function renderInsight(data) {
  const cases = data.insights.res_e_over_100 || [];
  document.getElementById("insight-text").textContent =
    "Çünkü bu, genel değil elektrik sektörü oranıdır: yenilenebilir elektrik üretimi ÷ " +
    "yurtiçi elektrik tüketimi. Hidroelektrik ağırlıklı net ihracatçı ülkelerde üretim, " +
    "tüketimi aşabildiği için oran %100'ü geçer. Bu bir veri hatası değildir — sektörleri " +
    "ayırmadan ortalama almak yanlış olur. Genel (overall) pay her zaman ≤ %100'dür.";
  const list = document.getElementById("insight-list");
  list.innerHTML = cases.map((c) =>
    `<li><b>${c.name}</b>: elektrik payı %${fmt(c.value)} (${c.year})</li>`).join("");
}

/* ---- Country explorer -------------------------------------------------- */
async function setupCountryExplorer(data) {
  const select = document.getElementById("country-select");
  const countries = [...data.countries].sort((a, b) => a.name.localeCompare(b.name, "tr"));
  select.innerHTML = countries.map((c) => `<option value="${c.geo}">${c.name}</option>`).join("");

  async function show(geo) {
    let c;
    try { c = await api(`/api/country/${encodeURIComponent(geo)}`); }
    catch (e) { return; }
    document.getElementById("country-stats").innerHTML = `
      <div class="stat"><span class="v">${fmt(c.latest_value)}%</span><span class="l">${c.latest_year} payı</span></div>
      <div class="stat"><span class="v">${c.cagr === null ? "—" : fmt(c.cagr, 1) + "%"}</span><span class="l">yıllık büyüme (CAGR)</span></div>
      <div class="stat"><span class="v">#${c.rank || "—"}</span><span class="l">sıralama (${data.reference_year})</span></div>`;
    const brand = css("--brand");
    draw("countryChart", {
      type: "line",
      data: { labels: c.trend.years,
        datasets: [{ label: `${c.name} — pay (%)`, data: c.trend.values,
          borderColor: brand, backgroundColor: hexA(brand, .1),
          borderWidth: 2.5, tension: .25, pointRadius: 2, fill: true }] },
      options: { maintainAspectRatio: false,
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: (x) => ` ${fmt(x.parsed.y)}%` } } },
        scales: { y: { ticks: { callback: (v) => v + "%" }, grid: { color: hexA(css("--text-muted"), .12) } },
          x: { grid: { display: false } } } },
    });
  }
  select.addEventListener("change", () => show(select.value));
  const first = countries.find((c) => c.geo === "TR") || countries[0];
  select.value = first.geo;
  show(first.geo);
}

/* ---- Footer ------------------------------------------------------------ */
function renderFooter(meta) {
  document.getElementById("footer-meta").innerHTML =
    `Kaynak: ${meta.source} · Lisans: ${meta.license} · ` +
    `Üretim: ${meta.generated_at} · Referans yıl: ${meta.reference_year}`;
  document.getElementById("source-badge").textContent = "Kaynak: Eurostat · " + meta.reference_year;
}

/* ---- helpers ----------------------------------------------------------- */
// Turn a hex/computed color into rgba with alpha (handles #rgb/#rrggbb).
function hexA(color, alpha) {
  let c = color.trim();
  if (c.startsWith("#")) {
    if (c.length === 4) c = "#" + [...c.slice(1)].map((x) => x + x).join("");
    const r = parseInt(c.slice(1, 3), 16), g = parseInt(c.slice(3, 5), 16), b = parseInt(c.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  return color; // already rgb()/named — used as-is
}

/* ---- boot -------------------------------------------------------------- */
async function main() {
  applyChartTheme();
  try {
    const summary = await api("/api/summary");
    const ranking = await api("/api/ranking?limit=37");
    // Decorate with convenience fields for the KPI/leader + explorer dropdown.
    summary.reference_year = summary.meta.reference_year;
    summary.ranking_top = ranking.ranking[0];
    summary.countries = ranking.ranking.map((r) => ({ geo: r.geo, name: r.name }));

    renderKpis(summary);
    renderProgress(summary);
    renderTrend(summary);
    renderRanking(summary, ranking);
    renderSectors(summary);
    renderInsight(summary);
    renderFooter(summary.meta);
    await setupCountryExplorer(summary);
  } catch (err) {
    document.querySelector(".wrap").insertAdjacentHTML("afterbegin",
      `<div class="card" style="border-color:var(--danger)"><b>Veri yüklenemedi.</b> ` +
      `Önce <code>python scripts/build_data.py</code> çalıştırıp API'yi başlatın.</div>`);
  }
}
document.addEventListener("DOMContentLoaded", main);
