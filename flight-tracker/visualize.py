import folium
from streamlit_folium import st_folium

def plot_flights(df):
    m = folium.Map(location=[40, 10], zoom_start=2)

    for _, row in df.iterrows():
        tooltip = f"{row['callsign']} - {row['origin_country']}"
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            tooltip=tooltip,
            icon=folium.Icon(color='blue', icon='plane', prefix='fa')
        ).add_to(m)

    return m