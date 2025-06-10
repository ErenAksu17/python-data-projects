import os

print("1️⃣ Sahte veri üretiliyor...")
os.system("python data_generator.py")

print("2️⃣ Model eğitiliyor...")
os.system("python model.py")

print("3️⃣ Anomali tespiti yapılıyor...")
os.system("python detect_anomalies.py")

print("3️⃣ Canlı Veri Aktarılıyor...")
os.system("streamlit_app.py")