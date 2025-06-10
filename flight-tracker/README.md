# ✈️ Flight Tracker

Gerçek zamanlı uçuşları görselleştiren Python tabanlı bir Streamlit uygulaması.  
OpenSky Network API kullanılarak uçakların konumu, ülke bilgisi ve hızı gibi veriler harita üzerinde gösterilir.

🔗 [Canlı Demo](https://flight-tracker-amsgn7wuwjjhs2n4ofrd23.streamlit.app)
---

## 📸 Örnek Ekran

![image](https://github.com/user-attachments/assets/64d77a2b-e80e-497b-92fb-7793e9672a99)

![image](https://github.com/user-attachments/assets/a24717e7-a585-437a-9ee1-7f24f2129fde)

---

## 🚀 Özellikler

- 🌍 Gerçek zamanlı uçuş verisi çekme (OpenSky API)
- 🗺️ Harita üzerinde uçak konumlarını gösterme
- 📊 Çağrı kodu, ülke, irtifa, hız gibi bilgileri tablo halinde sunma
- 🔁 Anlık veri yenileme desteği (opsiyonel)

---

## 🧠 Kullanılan Teknolojiler

- Python
- Streamlit
- Pandas
- Folium
- streamlit-folium
- OpenSky REST API

---

## 🛠️ Kurulum

```bash
git clone https://github.com/kullaniciadiniz/flight-tracker.git
cd flight-tracker
pip install -r requirements.txt
streamlit run app.py
```

---

## 📦 Dosya Yapısı

```bash
flight-tracker/
├── app.py                 # Ana uygulama
├── fetch_data.py          # API'den veri çeker
├── visualize.py           # Harita çizimi
├── requirements.txt       # Bağımlılıklar
└── README.md              # Bu dosya
```

---

## 🔗 Veri Kaynağı

OpenSky Network API

--

## ⚠️ Notlar

-API genel kullanımda rate limit'e takılabilir. Çok sık veri çekmekten kaçının.

-Gerçek zamanlı harita konumları yaklaşık 10-20 saniye gecikmeli olabilir.
