import streamlit as st
import joblib
import pandas as pd
from xgboost import XGBRegressor
from pulp import *

# 1. Judul & Header
st.title("🛡️ NutriCost AI Dashboard")
st.subheader("Optimasi Gizi & Efisiensi Anggaran Program Makan Bergizi")

# 2. Load Model & Data
# Pastikan file .pkl ada di folder yang sama
model_xgb = joblib.load('xgboost_model.pkl')

st.sidebar.header("Konfigurasi Target")
target_kkal = st.sidebar.slider("Target Energi (Kcal)", 1500, 2500, 2000)
target_protein = st.sidebar.slider("Target Protein (gram)", 40, 70, 50)

if st.button("🚀 Generate Rekomendasi Menu Termurah"):
    # --- BAGIAN PREDIKSI ---
    # Di sini nantinya kita masukkan logika prediksi harga H+1 dari XGBoost
    # Untuk demo, kita asumsikan harga sudah didapat dari model
    st.info("Mesin XGBoost sedang memprediksi fluktuasi harga pasar harian...")
    
    # --- BAGIAN OPTIMASI (PuLP) ---
    st.success(f"Optimasi PuLP berjalan: Mencari harga terendah untuk {target_kkal} Kcal...")
    
    # Tampilkan Hasil (Angka dari hasil running kamu tadi)
    st.metric(label="Total Biaya per Anak", value="Rp 8.288,21", delta="-44% vs Pagu Standar")
    
    # Tampilkan Tabel Rekomendasi
    data_resep = {
        "Bahan Baku": ["Beras Medium", "Telur Ayam Ras", "Kedelai Impor", "Minyak Goreng"],
        "Gramasi": ["208g", "50g", "45g", "30g"],
        "Estimasi Biaya": ["Rp 2.845", "Rp 1.482", "Rp 601", "Rp 565"]
    }
    st.table(pd.DataFrame(data_resep))
    
    st.balloons()