# 🤖 AI Tabanlı Sanal Fabrika Dashboard

Bu proje, **Streamlit** kullanılarak geliştirilmiş bir canlı simülasyon sistemidir.  
Amaç: Üretilen sentetik vibrasyon verisi üzerinde **Autoencoder tabanlı anomali tespiti** yapmak.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge.svg)](https://python-data-projects-4k6rgpquqe2jynjngz4qdb.streamlit.app)

---

## 🚀 Özellikler

- 📈 Gerçek zamanlı vibrasyon verisi simülasyonu
- 🧠 Autoencoder model ile anomaly detection
- 🔴 Anomaliler log olarak gösterilir
- 📊 Canlı grafikler ile sensör takibi
- ⏱️ 0.5 saniyelik güncellemeler ile gerçek zaman hissi

---

## 🧠 Kullanılan Teknolojiler

- Python
- Streamlit
- PyTorch
- Matplotlib
- NumPy

```python
📊 Canlı grafikler
🔴 Anomaliler ayrı renkle gösterilir
🧠 Model gerçek zamanlı karar verir
```

---

## ⚙️ Kurulum

```
git clone https://github.com/ErenAksu17/python-data-projects.git
cd python-data-projects/SyntheticData+AI
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## 📁 Dosya Yapısı

```
SyntheticData+AI/
├── streamlit_app.py     # Uygulama ana dosyası
├── model.py             # Autoencoder modeli
└── README.md            # Bu dosya
```

---

## 📌 Notlar

-Model eğitimi bu projede dahil değil — model sıfırdan başlıyor.

-model.pth dosyası gerekmediği için kaldırılmıştır.
