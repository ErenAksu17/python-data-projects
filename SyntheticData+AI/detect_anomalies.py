import torch
import pandas as pd
import numpy as np
from model import Autoencoder
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

def detect(data_path="vibration_data.csv", model_path="model.pth"):
    df = pd.read_csv(data_path)
    scaler = StandardScaler()
    df["vibration_scaled"] = scaler.fit_transform(df[["vibration"]])
    X = df[["vibration_scaled"]].values.astype("float32")

    model = Autoencoder()
    model.load_state_dict(torch.load(model_path))
    model.eval()

    with torch.no_grad():
        inputs = torch.tensor(X)
        outputs = model(inputs)
        loss = torch.mean((outputs - inputs) ** 2, dim=1).numpy()

    df["reconstruction_error"] = loss
    threshold = np.percentile(df[df["anomaly"] == 0]["reconstruction_error"], 95)
    df["predicted_anomaly"] = df["reconstruction_error"] > threshold

    print(classification_report(df["anomaly"], df["predicted_anomaly"]))
    df.to_csv("vibration_results.csv", index=False)
    print("✔️ Anomali tespiti tamamlandı. vibration_results.csv oluşturuldu.")

if __name__ == "__main__":
    detect()
