# ✈️ Flight Tracker

Gerçek zamanlı uçuşları görselleştiren Python tabanlı bir Streamlit uygulaması.  
OpenSky Network API kullanılarak uçakların konumu, ülke bilgisi ve hızı gibi veriler harita üzerinde gösterilir.

[Streamlit ile açmak için](https://flight-tracker-amsgn7wuwjjhs2n4ofrd23.streamlit.app)

---

## 📸 Örnek Ekran

![takip](https://github.com/user-attachments/assets/a712b2bb-a95c-4935-97e5-5fb64110110f)

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
git clone https://github.com/ErenAksu17/flight-tracker.git
cd flight-tracker
pip install -r requirements.txt
streamlit run app.py
```

---

## 📦 Dosya Yapısı
```
flight-tracker/
├── app.py                 # Ana uygulama
├── fetch_data.py          # API'den veri çeker
├── visualize.py           # Harita çizimi
├── requirements.txt       # Bağımlılıklar
└── README.md              # Bu dosya
```

---

🔗 Veri Kaynağı

-OpenSky Network API

---

⚠️ Notlar

-API genel kullanımda rate limit'e takılabilir. Çok sık veri çekmekten kaçının.

-Gerçek zamanlı harita konumları yaklaşık 10-20 saniye gecikmeli olabilir.
