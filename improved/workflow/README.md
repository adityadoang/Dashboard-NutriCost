# 🍚 NutriCost: Prediksi Harga Pangan & Optimasi Menu Bergizi Murah

> **METC Datathon 2026** — Solusi berbasis Machine Learning & Linear Programming untuk menekan biaya pemenuhan gizi anak dan mencegah stunting.

---

## 📋 Daftar Isi

- [Ringkasan Proyek](#-ringkasan-proyek)
- [Arsitektur Pipeline](#-arsitektur-pipeline)
- [Struktur Direktori](#-struktur-direktori)
- [Dataset](#-dataset)
- [Tahap 1: Training Model Prediksi Harga](#-tahap-1-training-model-prediksi-harga-modelipynb)
- [Tahap 2: Optimasi Menu Diet](#-tahap-2-optimasi-menu-diet-pulp_modelipynb)
- [Hasil Eksperimen](#-hasil-eksperimen)
- [Cara Menjalankan](#-cara-menjalankan)
- [Teknologi yang Digunakan](#-teknologi-yang-digunakan)
- [Limitasi & Pengembangan](#-limitasi--pengembangan-selanjutnya)

---

## 🎯 Ringkasan Proyek

**Masalah:** Stunting pada anak di Indonesia masih menjadi persoalan serius. Salah satu penyebabnya adalah ketidakmampuan keluarga miskin untuk memenuhi kebutuhan gizi harian anak karena harga pangan yang fluktuatif.

**Solusi:** Sistem NutriCost menjawab pertanyaan:
> *"Dengan harga pangan besok yang diprediksi, menu apa yang paling murah namun tetap memenuhi kebutuhan gizi anak?"*

Pipeline ini bekerja dalam **2 tahap**:
1. **Prediksi Harga** — Model XGBoost memprediksi harga 17 komoditas pangan pokok untuk hari berikutnya
2. **Optimasi Menu** — PuLP (Linear Programming) mencari kombinasi bahan makanan termurah yang memenuhi target gizi minimum

---

## 🏗 Arsitektur Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TRAINING PHASE                               │
│                        (model.ipynb)                                │
│                                                                     │
│  dataset_transformed.csv                                            │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────┐     ┌───────────────────┐                      │
│  │ Feature Engine.  │────▶│  XGBoost Training │ × 17 komoditas      │
│  │ - Lag features   │     │  (per komoditas)  │                      │
│  │ - Rolling mean   │     │  80/20 time split │                      │
│  │ - Differencing   │     └────────┬──────────┘                      │
│  └─────────────────┘              │                                  │
│                                   ▼                                  │
│                    trained_models/ (17 model .pkl)                    │
│                    metadata_komoditas.pkl                             │
│                                                                     │
│  Evaluasi: MAPE XGBoost = 0.30% vs Baseline SMA = 0.87%            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       INFERENCE + OPTIMIZATION                      │
│                       (pulp_model.ipynb)                            │
│                                                                     │
│  trained_models/ ──▶ Prediksi Harga Besok (17 komoditas)            │
│                      + Inverse Differencing                         │
│                              │                                      │
│  dataset_gizi.csv ──────────┐│                                      │
│                             ▼▼                                      │
│                    ┌─────────────────┐                               │
│                    │  PuLP Solver    │                               │
│                    │  Minimize Cost  │                               │
│                    │  s.t. Nutrisi   │                               │
│                    └────────┬────────┘                               │
│                             │                                       │
│                             ▼                                       │
│                    Rekomendasi Menu Optimal                          │
│                    (gramatur + biaya per anak)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Direktori

```
improved/workflow/
├── model.ipynb                  # Notebook training & evaluasi XGBoost
├── pulp_model.ipynb             # Notebook prediksi harga + optimasi diet
├── dataset_transformed.csv      # Dataset hasil feature engineering
├── dataset_gizi.csv             # Data nutrisi per komoditas (per kg)
├── trained_models/              # Direktori model tersimpan
│   ├── metadata_komoditas.pkl   # Dict: {nama_komoditas: diff_order}
│   ├── xgb_model_Beras_Medium.pkl
│   ├── xgb_model_Cabai_Merah_Keriting.pkl
│   ├── xgb_model_Daging_Ayam_Ras.pkl
│   ├── xgb_model_Telur_Ayam_Ras.pkl
│   └── ... (17 model total)
└── README.md                    # Dokumentasi ini
```

---

## 📊 Dataset

### `dataset_transformed.csv`
Dataset utama hasil feature engineering. Berisi **1565 baris** untuk **17 komoditas** pangan pokok.

| Kolom | Deskripsi |
|---|---|
| `variant_id` | ID unik komoditas |
| `variant_nama` | Nama komoditas (misal: "Beras Medium") |
| `tanggal` | Tanggal observasi harga |
| `harga` | Harga asli dalam Rupiah per kg |
| `harga_final` | Target prediksi (harga setelah differencing) |
| `diff_order` | Orde differencing (0, 1, atau 2) |
| `day`, `day_of_week`, `week_of_year` | Fitur temporal |
| `is_month_start`, `is_weekend` | Fitur biner temporal |
| `lag_1` s.d. `lag_14` | Lag features dari `harga_final` |
| `rolling_mean_3d`, `rolling_mean_7d` | Rata-rata bergerak |

### `dataset_gizi.csv`
Data kandungan nutrisi per **kilogram** untuk 16 komoditas.

| Kolom | Satuan | Contoh (Beras Medium) |
|---|---|---|
| `Energi` | Kkal/kg | 3570 |
| `Protein` | gram/kg | 84 |
| `Lemak` | gram/kg | 17 |
| `Karbohidrat` | gram/kg | 771 |
| `Serat` | gram/kg | 2 |

### 17 Komoditas yang Diprediksi

| No | Komoditas | Diff Order |
|---|---|---|
| 1 | Beras SPHP Bulog | 0 |
| 2 | Beras Medium | 1 |
| 3 | Beras Premium | 1 |
| 4 | Gula Pasir Curah | 1 |
| 5 | Minyak Goreng Sawit Curah | 1 |
| 6 | Minyak Goreng Sawit Kemasan Premium | 1 |
| 7 | Minyakita | 1 |
| 8 | Daging Sapi Paha Belakang | 1 |
| 9 | Daging Ayam Ras | 1 |
| 10 | Telur Ayam Ras | 2 |
| 11 | Tepung Terigu | 1 |
| 12 | Kedelai Impor | 1 |
| 13 | Cabai Merah Keriting | 0 |
| 14 | Cabai Merah Besar | 1 |
| 15 | Cabai Rawit Merah | 1 |
| 16 | Bawang Merah | 1 |
| 17 | Bawang Putih Honan | 1 |

---

## 🤖 Tahap 1: Training Model Prediksi Harga (`model.ipynb`)

### Pendekatan

Setiap komoditas di-training dengan **model XGBoost terpisah**. Pendekatan per-komoditas dipilih karena setiap bahan pangan memiliki pola harga yang berbeda (misal: cabai sangat volatil, beras relatif stabil).

### Feature Engineering

| Kategori | Fitur | Deskripsi |
|---|---|---|
| **Temporal** | `day`, `day_of_week`, `week_of_year` | Pola mingguan dan harian |
| **Biner** | `is_month_start`, `is_weekend` | Event khusus |
| **Lag** | `lag_1` s.d. `lag_9`, `lag_11`, `lag_14` | Harga historis |
| **Rolling** | `rolling_mean_3d`, `rolling_mean_7d` | Tren jangka pendek |

### Differencing

Untuk membuat time series lebih stasioner, diterapkan differencing dengan orde berbeda per komoditas:
- **Order 0**: Prediksi langsung harga asli (untuk seri yang sudah stasioner)
- **Order 1**: Prediksi selisih harga `Δh = h(t) - h(t-1)`
- **Order 2**: Prediksi selisih kedua `Δ²h = Δh(t) - Δh(t-1)`

### Hyperparameter XGBoost

```python
XGBRegressor(
    n_estimators=100,
    learning_rate=0.1,
    max_depth=5,
    random_state=42
)
```

### Evaluasi

Time-based split **80% training / 20% testing** untuk setiap komoditas. Dibandingkan dengan baseline **SMA 7-hari**.

| Metrik | XGBoost | Baseline (SMA) |
|---|---|---|
| **Rata-rata MAPE** | **0.2957%** | 0.8708% |
| Std MAPE | 0.3505% | 1.0773% |
| Min MAPE | 0.0257% | 0.0301% |
| Max MAPE | 1.2077% | 3.2258% |

**XGBoost unggul 3× lipat** dibandingkan baseline secara rata-rata.

### Output

- **17 model** `.pkl` tersimpan di `trained_models/`
- **Metadata** `metadata_komoditas.pkl` berisi mapping `{komoditas: diff_order}`

---

## 🥗 Tahap 2: Optimasi Menu Diet (`pulp_model.ipynb`)

### Alur Proses

1. **Load model** yang sudah di-train dan dataset
2. **Prediksi harga besok** untuk setiap komoditas menggunakan data terakhir
3. **Inverse differencing** untuk mengubah prediksi diff menjadi harga Rupiah
4. **Optimasi linear** menggunakan PuLP untuk menemukan menu termurah

### Inverse Differencing

```python
if diff_order == 0:
    harga_prediksi = prediksi_langsung
elif diff_order == 1:
    harga_prediksi = harga_kemarin + prediksi_diff
elif diff_order == 2:
    harga_prediksi = harga_kemarin + (harga_kemarin - harga_2hari_lalu) + prediksi_diff
```

### Formulasi Linear Programming

**Fungsi Objektif:**
```
Minimize: Σ (harga_prediksi[i] × kuantitas[i])  untuk semua komoditas i
```

**Kendala Gizi:**

| Constraint | Nilai | Tujuan |
|---|---|---|
| Energi | ≥ 700 Kkal | Kebutuhan kalori 1× makan anak |
| Protein | ≥ 20 gram | Pencegahan stunting |
| Protein Hewani | ≥ 30 gram | Wajib sumber protein hewani |

**Kendala Logika Manusia (batas kuantitas):**

| Komoditas | Min | Max | Keterangan |
|---|---|---|---|
| Beras | 50g (conditional) | 80g | Makanan pokok |
| Tepung Terigu | – | 15g | Pelengkap |
| Kedelai Impor | 20g | 40g | Wajib protein nabati |
| Daging Ayam / Telur | – | 60g | Protein hewani |
| Daging Sapi | – | 50g | Protein hewani |
| Gula | – | 8g | Batasi gula |
| Minyak Goreng | 2g (conditional) | 10g | Kebutuhan masak |
| Bawang | 2g | 6g | Bumbu |
| Cabai | – | 2g | Toleransi anak |

**Kendala Logika Bisnis:**

| Tipe | Deskripsi |
|---|---|
| **Mutual Exclusion** | Pilih maks 1 jenis minyak (curah / premium / Minyakita) |
| **Mutual Exclusion** | Pilih maks 1 jenis beras (premium / medium) |
| **Big-M Method** | Jika jenis tidak dipilih (biner=0), kuantitas dipaksa 0 |
| **Conditional Lower Bound** | Jika jenis dipilih (biner=1), kuantitas ≥ minimum tertentu |

---

## 📈 Hasil Eksperimen

### Prediksi Harga (Contoh Output)

```
Prediksi Harga Besok (Rp/kg):
  - Beras SPHP Bulog      : Rp  12,367.76
  - Cabai Rawit Merah      : Rp  60,381.63
  - Daging Sapi            : Rp 138,118.42
  - Telur Ayam Ras         : Rp  29,572.27
  - Beras Medium           : Rp  13,718.37
  ...
```

### Rekomendasi Menu Optimal (Contoh Output)

```
Total Biaya per Anak : Rp 3,903.93

Rekomendasi Resep & Gramatur:
- Bawang Merah..........     2 gram  (Rp     81)
- Gula Pasir Curah......     8 gram  (Rp    146)
- Minyakita.............    10 gram  (Rp    160)
- Tepung Terigu.........    15 gram  (Rp    187)
- Daging Ayam Ras.......    43 gram  (Rp  1,623)
- Bawang Putih Honan....     2 gram  (Rp     72)
- Kedelai Impor.........    40 gram  (Rp    538)
- Beras Medium..........    80 gram  (Rp  1,097)

[ Pencapaian Target Gizi ]
- Total Energi Terpenuhi   : 700.0 Kcal
- Total Protein Terpenuhi  : 28.0 gram
```

---

## 🚀 Cara Menjalankan

### Prasyarat

```bash
pip install pandas numpy xgboost scikit-learn joblib pulp matplotlib seaborn
```

### Langkah Eksekusi

1. **Training model** (jalankan sekali atau saat data berubah):
   ```
   Buka dan jalankan: improved/workflow/model.ipynb
   ```
   Output: `trained_models/` berisi 17 model + metadata

2. **Prediksi harga + optimasi menu** (jalankan setiap hari):
   ```
   Buka dan jalankan: improved/workflow/pulp_model.ipynb
   ```
   Output: Rekomendasi menu optimal dengan biaya minimum

---

## 🛠 Teknologi yang Digunakan

| Komponen | Teknologi | Versi |
|---|---|---|
| Bahasa | Python | 3.12.5 |
| ML Model | XGBoost (`XGBRegressor`) | – |
| Evaluasi | scikit-learn (MAPE, RMSE) | – |
| Optimasi | PuLP (Linear Programming) | – |
| Data | pandas, numpy | – |
| Visualisasi | matplotlib, seaborn | – |
| Serialisasi | joblib | – |

---

## ⚠️ Limitasi & Pengembangan Selanjutnya

### Limitasi Saat Ini

1. **Data terbatas** — ~92 titik data per komoditas; pola musiman jangka panjang mungkin belum tertangkap
2. **Evaluasi single split** — Belum menggunakan walk-forward validation
3. **Hyperparameter default** — XGBoost belum di-tune
4. **Komoditas terbatas** — Hanya 16 komoditas yang punya data nutrisi (Beras SPHP Bulog tidak termasuk dalam optimasi)
5. **Nutrisi tidak lengkap** — Constraint hanya mencakup Energi dan Protein; Lemak, Karbohidrat, dan Serat belum di-constraint karena keterbatasan variasi komoditas yang tersedia

### Rencana Pengembangan

- [ ] **Walk-forward validation** untuk evaluasi yang lebih robust
- [ ] **Hyperparameter tuning** menggunakan Optuna atau GridSearchCV
- [ ] **Ensemble model** — pilih XGBoost atau SMA per komoditas berdasarkan validation MAPE
- [ ] **Prediksi multi-step** — Perencanaan menu mingguan (7 hari ke depan)
- [ ] **Dashboard Streamlit** — Visualisasi interaktif rekomendasi menu harian
- [ ] **Tambah komoditas** — Sayur dan buah untuk memenuhi kebutuhan serat

---

## 👥 Tim

**METC Datathon 2026**

---

*Terakhir diperbarui: Mei 2026*
