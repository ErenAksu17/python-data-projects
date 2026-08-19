# ✈️ Flight Tracker

Uçakların gerçek zamanlı konumunu harita üzerinde gösteren bir uygulama.
*Real-time aircraft positions on an interactive map.*

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![Folium](https://img.shields.io/badge/Folium-77B829?style=flat-square&logo=leaflet&logoColor=white)
![OpenSky](https://img.shields.io/badge/OpenSky%20Network-0B3D91?style=flat-square)
![Durum](https://img.shields.io/badge/durum-yeniden%20yazılıyor-orange?style=flat-square)

> **ℹ️ Durum notu / Status**
> Buradaki sürüm **Streamlit** tabanlıdır ve çalışır durumdadır, ancak eski barındırma
> bağlantısı kapatıldığı için canlı demo şu an yayında değil. Proje hâlihazırda
> **FastAPI + Leaflet** olarak yeniden yazılıyor (uçuş izleri, acil durum squawk uyarıları,
> takip modu). Yeni sürüm hazır olduğunda bu klasör güncellenecek.
>
> *The version here is the working Streamlit build; its old hosted demo has been taken
> down. A FastAPI + Leaflet rewrite is in progress and will replace this folder.*

**Diller / Languages / Lingue:** [🇹🇷 Türkçe](#-türkçe) · [🇬🇧 English](#-english) · [🇮🇹 Italiano](#-italiano)

---

## 🇹🇷 Türkçe

OpenSky Network API'sini kullanarak uçakların konumu, kalkış ülkesi ve hızı gibi verileri
harita üzerinde gösteren Python tabanlı bir Streamlit uygulaması.

### 📸 Ekran görüntüleri

![Harita görünümü](https://github.com/user-attachments/assets/64d77a2b-e80e-497b-92fb-7793e9672a99)
![Tablo görünümü](https://github.com/user-attachments/assets/a24717e7-a585-437a-9ee1-7f24f2129fde)

### 🚀 Özellikler

- 🌍 Gerçek zamanlı uçuş verisi (OpenSky API)
- 🗺️ Uçak konumlarını etkileşimli haritada gösterme
- 📊 Çağrı kodu, ülke, irtifa ve hız bilgilerini tablo hâlinde sunma
- 🔁 Opsiyonel canlı veri yenileme

### 🧠 Kullanılan teknolojiler

`Python` · `Streamlit` · `Pandas` · `Folium` · `streamlit-folium` · `OpenSky REST API`

### 🛠️ Kurulum

```bash
git clone https://github.com/ErenAksu17/python-data-projects.git
cd python-data-projects/flight-tracker
pip install -r requirements.txt
streamlit run app.py
```

### 📦 Dosya yapısı

```text
flight-tracker/
├── app.py             # Ana uygulama
├── fetch_data.py      # API'den veri çeker
├── visualize.py       # Harita çizimi
├── img/               # Ekran görüntüleri
├── requirements.txt   # Bağımlılıklar
└── README.md          # Bu dosya
```

### 🔗 Veri kaynağı

[OpenSky Network API](https://opensky-network.org/) — *not: OpenSky artık anonim
erişimi kısıtlıyor, yoğun kullanımda OAuth2 kimlik doğrulaması gerekebilir.*

### ⚠️ Notlar

- Herkese açık API'nin sorgu limiti vardır; aşırı istekten kaçının.
- Haritadaki konumlar yaklaşık 10–20 saniye gecikmeli olabilir.

---

## 🇬🇧 English

A Python/Streamlit app that visualizes real-time flights. Using the OpenSky Network API,
it shows aircraft data such as position, country of origin and speed on a map.

### 📸 Screenshots

![Map view](https://github.com/user-attachments/assets/64d77a2b-e80e-497b-92fb-7793e9672a99)
![Table view](https://github.com/user-attachments/assets/a24717e7-a585-437a-9ee1-7f24f2129fde)

### 🚀 Features

- 🌍 Fetches real-time flight data (via the OpenSky API)
- 🗺️ Displays aircraft positions on an interactive map
- 📊 Shows callsign, origin country, altitude and speed in a table
- 🔁 Optional live-refresh support

### 🧠 Tech stack

`Python` · `Streamlit` · `Pandas` · `Folium` · `streamlit-folium` · `OpenSky REST API`

### 🛠️ Setup

```bash
git clone https://github.com/ErenAksu17/python-data-projects.git
cd python-data-projects/flight-tracker
pip install -r requirements.txt
streamlit run app.py
```

### 📦 Project structure

```text
flight-tracker/
├── app.py             # Main app
├── fetch_data.py      # Fetches data from the API
├── visualize.py       # Map rendering logic
├── img/               # Screenshots
├── requirements.txt   # Dependencies
└── README.md          # This file
```

### 🔗 Data source

[OpenSky Network API](https://opensky-network.org/) — *note: OpenSky now restricts
anonymous access; heavy use may require OAuth2 authentication.*

### ⚠️ Notes

- The public API is rate-limited; avoid excessive requests.
- Map positions may lag by roughly 10–20 seconds.

---

## 🇮🇹 Italiano

Un'app Streamlit basata su Python che visualizza i voli in tempo reale. Utilizza l'API di
OpenSky Network per mostrare dati sugli aerei come posizione, paese d'origine e velocità su una mappa.

### 📸 Screenshot

![Vista mappa](https://github.com/user-attachments/assets/64d77a2b-e80e-497b-92fb-7793e9672a99)
![Vista tabella](https://github.com/user-attachments/assets/a24717e7-a585-437a-9ee1-7f24f2129fde)

### 🚀 Caratteristiche

- 🌍 Recupera dati di volo in tempo reale (tramite OpenSky API)
- 🗺️ Mostra la posizione degli aerei su una mappa interattiva
- 📊 Visualizza callsign, paese d'origine, altitudine e velocità in una tabella
- 🔁 Supporto opzionale per l'aggiornamento in tempo reale

### 🧠 Tecnologie utilizzate

`Python` · `Streamlit` · `Pandas` · `Folium` · `streamlit-folium` · `OpenSky REST API`

### 🛠️ Setup

```bash
git clone https://github.com/ErenAksu17/python-data-projects.git
cd python-data-projects/flight-tracker
pip install -r requirements.txt
streamlit run app.py
```

### 🔗 Fonte dati

[OpenSky Network API](https://opensky-network.org/)

---

<div align="center">
<sub>📂 <a href="../README.md">Python Data Projects</a> koleksiyonunun bir parçasıdır.</sub>
</div>
