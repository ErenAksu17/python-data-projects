<div align="center">

# 🧠 Python Data Projects

**Veri bilimi, analiz ve görselleştirme projelerim — hepsi tek çatı altında.**

*My data-science, analysis and visualization work, collected in one repository.*

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?style=flat-square&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=flat-square&logo=numpy&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB)
![Jupyter](https://img.shields.io/badge/Jupyter-F37626?style=flat-square&logo=jupyter&logoColor=white)

[![CI](https://github.com/ErenAksu17/python-data-projects/actions/workflows/ci.yml/badge.svg)](https://github.com/ErenAksu17/python-data-projects/actions)
[![Lisans](https://img.shields.io/badge/Lisans-MIT-22c55e?style=flat-square)](LICENSE)

**Diller / Languages:** [🇹🇷 Türkçe](#-türkçe) · [🇬🇧 English](#-english)

</div>

---

## 📂 Projeler / Projects

Her klasör kendi başına çalışan bağımsız bir projedir.
*Each folder is a standalone project with its own README and dependencies.*

| Proje | Ne yapıyor / What it does | Yığın / Stack | Durum |
|:--|:--|:--|:--|
| 📡 **[Virtual Factory](./SyntheticData%2BAI)**<br/><sub>Titreşim anomali tespiti</sub> | Döner makineler için durum izleme: fizik temelli rulman titreşim simülatörü, **yalnızca sağlıklı veriyle** eğitilmiş tek sınıflı otokodlayıcı, zarf spektrumuyla arıza teşhisi ve backend olsun olmasın çalışan canlı arayüz.<br/><sub>*Condition monitoring: physics-based bearing simulator, one-class autoencoder, envelope-spectrum diagnosis, live dashboard.*</sub> | `PyTorch` `FastAPI` `WebSocket` `React` | ✅ Aktif |
| 🌿 **[Renewable Energy Analyzer](./renewable-energy-analyzing)**<br/><sub>AB-27 yenilenebilir enerji</sub> | **Gerçek Eurostat verisiyle** AB-27 yenilenebilir enerji payı analizi: güvenli veri hattı, sıkılaştırılmış FastAPI API'si ve interaktif dashboard. Tahmin dürüst — naif modeli geçen, doğrulanmış bir trend.<br/><sub>*EU-27 renewable share from real Eurostat data: secure pipeline, hardened API, interactive dashboard.*</sub> | `pandas` `FastAPI` `React` `Tailwind` | ✅ Aktif |
| ✈️ **[Flight Tracker](./flight-tracker)**<br/><sub>Canlı uçuş takibi</sub> | OpenSky Network API'siyle uçakların konumunu, kalkış ülkesini ve hızını harita üzerinde gösterir.<br/><sub>*Real-time aircraft positions on an interactive map, via the OpenSky Network API.*</sub> | `Streamlit` `Folium` `OpenSky` | 🔧 Yeniden yazılıyor |
| 🚗 **[2020 Otomobil Pazarı](./2020-turkey-car-market)**<br/><sub>Pazar analizi</sub> | 2020'de Türkiye'de satılan otomobillerin marka, model ve segment kırılımıyla analizi ve görselleştirilmesi.<br/><sub>*Brand-, model- and segment-level analysis of the 2020 Turkish car market.*</sub> | `pandas` `Matplotlib` `Seaborn` | 📘 Tamamlandı |

> 🔧 **Flight Tracker notu:** Streamlit sürümü çalışıyor, ancak eski barındırma bağlantısı
> kapatıldı. Proje şu anda FastAPI + Leaflet olarak yeniden yazılıyor; yeni sürüm hazır
> olduğunda bu klasör güncellenecek.

---

## 🗂️ Depo yapısı / Repository layout

```text
python-data-projects/
├── SyntheticData+AI/            # 📡 Virtual Factory — titreşim anomali tespiti
│   ├── src/                     #    simülatör, öznitelik çıkarımı, model, API
│   ├── frontend/                #    React + Vite + Tailwind arayüz
│   ├── tests/                   #    pytest + TS↔Python sayısal parite testi
│   └── docs/
├── renewable-energy-analyzing/  # 🌿 Eurostat yenilenebilir enerji analizi
│   ├── src/                     #    veri hattı ve analiz
│   ├── api/                     #    sıkılaştırılmış FastAPI servisi
│   ├── frontend/                #    interaktif dashboard
│   └── tests/
├── flight-tracker/              # ✈️ Canlı uçuş haritası
├── 2020-turkey-car-market/      # 🚗 Jupyter not defteri analizi
└── README.md                    # 📄 Bu dosya
```

---

## 🇹🇷 Türkçe

### ⚙️ Kurulum

Projelerin her biri bağımsızdır — kökte tek bir kurulum yoktur:

```bash
git clone https://github.com/ErenAksu17/python-data-projects.git
cd python-data-projects/<proje-adi>
pip install -r requirements.txt   # varsa
```

Her projenin kendi README'sinde nasıl çalıştırılacağı adım adım anlatılıyor.

### 🧭 Yaklaşım

- **Gerçek veri.** Eurostat, OpenSky ve kamuya açık pazar verileri — sentetik demo verisi değil.
  *(Virtual Factory'nin simülatörü bilinçli bir istisnadır: fiziği bilinen bir arıza üretmek için var.)*
- **Dürüst çıktı.** Tahminler doğrulanır; naif modeli geçemeyen bir tahmin yayınlanmaz.
- **Testler kapıdır.** Aktif projelerde pytest + CI zorunlu.

---

## 🇬🇧 English

### ⚙️ Setup

Every project stands on its own — there is no single root install:

```bash
git clone https://github.com/ErenAksu17/python-data-projects.git
cd python-data-projects/<project-name>
pip install -r requirements.txt   # if present
```

Each project's own README documents how to run it.

### 🧭 Approach

- **Real data.** Eurostat, OpenSky and public market data — not synthetic demo filler.
  *(Virtual Factory's simulator is a deliberate exception: it exists to produce faults whose physics is known.)*
- **Honest output.** Forecasts are validated; a forecast that cannot beat a naive baseline is not published.
- **Tests are a gate.** pytest + CI are required on the active projects.

---

## 📄 Lisans / License

[MIT](LICENSE) — © 2025-2026 Eren AKSU. Kod serbestçe kullanılabilir; telif bildirimini koruyun.
Analiz edilen **veri kümeleri kendi kaynaklarının lisansına tabidir** (Eurostat: CC BY 4.0,
OpenSky: kendi kullanım şartları) — lisans bunları kapsamaz.

*Code is MIT; the analysed datasets remain under their own source licences.*

---

<div align="center">
<sub>👤 <a href="https://github.com/ErenAksu17">ErenAksu17</a> · Geri bildirime her zaman açığım / Feedback always welcome</sub>
</div>
