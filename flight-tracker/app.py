import streamlit as st
import pandas as pd
from fetch_data import fetch_flights
from visualize import plot_flights
from streamlit_folium import st_folium

st.set_page_config(page_title="Flight Tracker", layout="wide")
st.title("✈️ Gerçek Zamanlı Uçuş Takip Uygulaması")

st.markdown("OpenSky API kullanılarak güncel uçuş verileri çekilir ve harita üzerinde gösterilir.")

# Veriyi çek
df = fetch_flights()

if df.empty:
    st.error("Uçuş verisi alınamadı. API şu anda yanıt vermiyor olabilir.")
else:
    st.success(f"{len(df)} uçuş bulundu.")
    st.dataframe(df[["callsign", "origin_country", "latitude", "longitude", "baro_altitude"]])

    st.markdown("### 🌍 Harita Görselleştirme")
    m = plot_flights(df)
    st_folium(m, width=1000, height=600)