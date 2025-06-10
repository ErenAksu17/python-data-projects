import streamlit as st
import pandas as pd
import torch
from model import Autoencoder
import numpy as np
import time
import matplotlib.pyplot as plt

# Model yükle
model = Autoencoder()
#model.load_state_dict(torch.load("model.pth"))
model.eval()

# Anomali eşiği (model eğitimi sonucu belirlenmiş olabilir)
ANOMALY_THRESHOLD = 0.1

# Başlık
st.title("🧠 AI Tabanlı Sanal Fabrika Dashboard")
st.markdown("Canlı vibrasyon verisi simülasyonu ve anomali tespiti")

# Placeholder'lar
chart_placeholder = st.empty()
log_placeholder = st.empty()

# Simülasyon
data_buffer = []

for i in range(1000):  # Canlı gibi göstermek için döngü
    # Sahte veri üret
    vibration = np.random.normal(0, 1) if np.random.rand() > 0.05 else np.random.normal(5, 1)
    data_buffer.append(vibration)

    # Model ile tespit
    input_tensor = torch.tensor([vibration], dtype=torch.float32).unsqueeze(0)
    output = model(input_tensor)
    loss = torch.nn.functional.mse_loss(output, input_tensor).item()
    is_anomaly = loss > ANOMALY_THRESHOLD

    # Log göster
    log_placeholder.markdown(
        f"**Yeni Veri #{i+1}:** `{vibration:.3f}` - {'🔴 ANOMALİ' if is_anomaly else '🟢 Normal'} (Loss: {loss:.4f})"
    )

    # Grafik
    df = pd.DataFrame(data_buffer, columns=["Vibration"])
    fig, ax = plt.subplots()
    df["Vibration"].plot(ax=ax, color="green")
    ax.axhline(4, color="red", linestyle="--", alpha=0.5)
    ax.set_ylabel("Vibration")
    ax.set_xlabel("Zaman")
    ax.set_title("Canlı Vibrasyon Verisi")
    chart_placeholder.pyplot(fig)

    time.sleep(0.5)  # Yavaş gösterim için

st.success("Simülasyon tamamlandı.")
