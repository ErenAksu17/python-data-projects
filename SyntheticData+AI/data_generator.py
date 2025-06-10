from faker import Faker
import numpy as np
import pandas as pd

fake = Faker()

def generate_vibration_data(n_samples=1000, anomaly_rate=0.05):
    data = []
    for _ in range(n_samples):
        normal = np.random.normal(loc=1.0, scale=0.1)
        is_anomaly = np.random.rand() < anomaly_rate
        value = normal * (np.random.uniform(1.5, 3.0) if is_anomaly else 1.0)
        data.append({
            "timestamp": fake.date_time(),
            "vibration": value,
            "anomaly": int(is_anomaly)
        })
    return pd.DataFrame(data)

if __name__ == "__main__":
    df = generate_vibration_data()
    df.to_csv("vibration_data.csv", index=False)

    print("Fake data was generated and saved to the Vibration_data.csv file.")