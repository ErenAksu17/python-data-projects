import requests
import pandas as pd

def fetch_flights():
    url = "https://opensky-network.org/api/states/all"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"Veri çekilemedi: {e}")
        return pd.DataFrame()

    raw = data.get("states", [])

    # 17 kolon var, biz sadece işimize yarayanları seçiyoruz
    df = pd.DataFrame(raw)
    df = df.rename(columns={
        0: "icao24",
        1: "callsign",
        2: "origin_country",
        5: "longitude",
        6: "latitude",
        7: "baro_altitude",
        8: "on_ground",
        9: "velocity"
    })
    
    df = df.dropna(subset=["latitude", "longitude"])
    return df[["icao24", "callsign", "origin_country", "latitude", "longitude", "baro_altitude", "on_ground", "velocity"]]
