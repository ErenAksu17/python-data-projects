# ✈️ Flight Tracker

A Python-based Streamlit app that visualizes real-time flights.
Using the OpenSky Network API, it displays aircraft data such as location, country of origin, and speed on a map.

🔗 [Live Demo]([https://flight-tracker-amsgn7wuwjjhs2n4ofrd23.streamlit.app](https://python-data-projects-h7phw8uqqxyfguhpruahfa.streamlit.app))
---

## 📸 Sample Screenshots

![image](https://github.com/user-attachments/assets/64d77a2b-e80e-497b-92fb-7793e9672a99)

![image](https://github.com/user-attachments/assets/a24717e7-a585-437a-9ee1-7f24f2129fde)

---

## 🚀 Features

- 🌍 Fetches real-time flight data (via OpenSky API)
- 🗺️ Displays aircraft positions on an interactive map
- 📊 Shows info like callsign, origin country, altitude, and speed in a table
- 🔁 Optional real-time data refresh support

---

## 🧠 Technologies Used

- Python
- Streamlit
- Pandas
- Folium
- streamlit-folium
- OpenSky REST API

---

## 🛠️ Setup

```bash
git clone https://github.com/kullaniciadiniz/flight-tracker.git
cd flight-tracker
pip install -r requirements.txt
streamlit run app.py
```

---

## 📦 Project Structure

```bash
flight-tracker/
├── app.py               # Main app
├── fetch_data.py        # Fetches data from the API
├── visualize.py         # Map rendering logic
├── requirements.txt     # Dependencies
└── README.md            # This file
```

---

## 🔗 Data Source

OpenSky Network API

--

## ⚠️ Notes

- The API has rate limits for public use. Avoid excessive requests.

- Real-time map positions may have a delay of around 10–20 seconds.
