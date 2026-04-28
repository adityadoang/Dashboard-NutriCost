import streamlit as st
import joblib
import pandas as pd
import os
from pulp import *
import plotly.express as px

# Konfigurasi Halaman
st.set_page_config(page_title="NutriCost AI", layout="wide")

# Custom CSS untuk desain profesional dan minimalis yang mendukung Light & Dark Mode
st.markdown("""
<style>
    /* Tipografi dasar */
    .main-title {
        font-size: 2.2rem;
        font-weight: 600;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-color);
    }
    .sub-title {
        font-size: 1.1rem;
        margin-bottom: 2.5rem;
        font-weight: 400;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-color);
        opacity: 0.8;
    }
    
    /* Tabel minimalis */
    .styled-table {
        border-collapse: collapse;
        margin: 10px 0 30px 0;
        font-size: 0.95rem;
        width: 100%;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-color);
    }
    .styled-table thead tr {
        background-color: var(--secondary-background-color);
        text-align: left;
        border-bottom: 2px solid rgba(128, 128, 128, 0.2);
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-color);
        opacity: 0.9;
    }
    .styled-table th, .styled-table td {
        padding: 16px 20px;
    }
    .styled-table tbody tr {
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        transition: background-color 0.15s ease;
    }
    .styled-table tbody tr:hover {
        background-color: rgba(128, 128, 128, 0.1);
    }
    
    /* Header Seksi */
    .section-header {
        font-size: 1.25rem;
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-color);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">NutriCost AI Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Optimasi Gizi & Efisiensi Anggaran Program Makan Bergizi Berbasis AI</div>', unsafe_allow_html=True)

# 2. Setup Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'trained_models')
DATA_CLEAN_PATH = os.path.join(BASE_DIR, 'dataset_clean.csv')
DATA_GIZI_PATH = os.path.join(BASE_DIR, 'dataset_gizi.csv')

# 3. Load Data & Predict Prices
@st.cache_data
def predict_prices():
    df = pd.read_csv(DATA_CLEAN_PATH)
    all_commodities = df['variant_nama'].unique()
    predicted_prices_tomorrow = {}
    
    for commodity in all_commodities:
        safe_filename = commodity.replace(" ", "_").replace("/", "_")
        model_path = os.path.join(MODEL_DIR, f"xgb_{safe_filename}.joblib")
        
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            
            df_model = df[df['variant_nama'] == commodity]
            features = ['day', 'day_of_week', 'is_weekend', 'price_lag_1', 'price_lag_2', 'price_lag_3', 'rolling_mean_7d']
            
            latest_features = df_model[features].iloc[-1:].copy() 
            tomorrow_price_pred = model.predict(latest_features)[0]
            
            predicted_prices_tomorrow[commodity] = float(tomorrow_price_pred)
            
    return predicted_prices_tomorrow

@st.cache_data
def load_nutrition_data():
    df_nutrition = pd.read_csv(DATA_GIZI_PATH)
    df_nutrition.set_index('KOMODITAS', inplace=True)
    return df_nutrition

def format_rupiah(angka):
    if angka >= 1e12:
        return f"Rp {angka/1e12:.2f} Triliun"
    elif angka >= 1e9:
        return f"Rp {angka/1e9:.2f} Miliar"
    elif angka >= 1e6:
        return f"Rp {angka/1e6:.2f} Juta"
    else:
        return f"Rp {angka:,.0f}"

def calculate_optimal_budget(prices_dict, target_kkal, target_protein, df_nutrition, available_items):
    if not available_items:
        return None, None, None, None

    lp_problem = LpProblem("NutriCost_Diet_Optimization", LpMinimize)
    x = LpVariable.dicts("qty_kg", available_items, lowBound=0, cat='Continuous')

    # ── VARIABEL BINER: Pilih hanya 1 jenis per grup ──────────────────────────
    pakai_minyak_curah   = LpVariable('Pakai_Minyak_Curah',   cat='Binary')
    pakai_minyak_premium = LpVariable('Pakai_Minyak_Premium', cat='Binary')
    pakai_minyakita      = LpVariable('Pakai_Minyakita',      cat='Binary')

    pakai_beras_premium  = LpVariable('Pakai_Beras_Premium',  cat='Binary')
    pakai_beras_medium   = LpVariable('Pakai_Beras_Medium',   cat='Binary')

    # 1. FUNGSI OBJEKTIF
    lp_problem += lpSum([prices_dict[i] * x[i] for i in available_items]), "Total_Cost"

    # 2. KENDALA GIZI
    lp_problem += lpSum([df_nutrition.loc[i, 'Energi'] * x[i] for i in available_items]) >= target_kkal, "Min_Energy"
    lp_problem += lpSum([df_nutrition.loc[i, 'Protein'] * x[i] for i in available_items]) >= target_protein, "Min_Protein"

    # 3. KENDALA LOGIKA MANUSIA (Porsi 1x Makan Siang Anak 6-12 Tahun)
    for i in available_items:
        # Makanan Pokok
        if 'Beras' in i:
            lp_problem += x[i] <= 0.100  # 100g = 1 centong nasi penuh (nasi cetak mangkok)
            # NOTE: Lower bound beras ditangani di bawah secara conditional via Big-M
        elif 'Terigu' in i:
            lp_problem += x[i] <= 0.020  # 20g = lapisan tepung ayam krispi / mendoan
        elif 'Gula' in i:
            lp_problem += x[i] <= 0.010  # 10g = batas pemanis dalam bumbu / minuman
        elif 'Minyak' in i:
            lp_problem += x[i] <= 0.010  # 10g = ~1 sendok makan (menumis & menggoreng)
        # Lauk & Protein
        elif 'Ayam' in i:
            lp_problem += x[i] <= 0.060  # 60g = 1 potong dada/paha ukuran sedang
        elif 'Sapi' in i:
            lp_problem += x[i] <= 0.050  # 50g = 2-3 potong daging rendang/semur kecil
        elif 'Telur' in i:
            lp_problem += x[i] <= 0.060  # 60g = 1 butir telur ayam ukuran besar
        elif 'Kedelai' in i:
            lp_problem += x[i] <= 0.025  # 25g = 1-2 potong tempe/tahu standar
        # Bumbu (Sangat Dibatasi)
        elif 'Bawang' in i:
            lp_problem += x[i] <= 0.005  # 5g = standar bumbu dapur 1 porsi masakan
        elif 'Cabai' in i:
            lp_problem += x[i] <= 0.003  # 3g = pemberi rasa/warna, ramah pencernaan anak

    protein_hewani_items = [i for i in available_items if 'Ayam' in i or 'Sapi' in i or 'Telur' in i]
    if protein_hewani_items:
        lp_problem += lpSum([x[i] for i in protein_hewani_items]) >= 0.050

    # ── CONSTRAINT MUTUAL EXCLUSION: Pilih Maks 1 Jenis per Grup ─────────────
    lp_problem += pakai_minyak_curah + pakai_minyak_premium + pakai_minyakita <= 1, 'Pilih_Maks_1_Minyak'
    lp_problem += pakai_beras_premium + pakai_beras_medium <= 1,                    'Pilih_Maks_1_Beras'

    # ── CONSTRAINT BIG-M: Hubungkan biner ke variabel gramatur ───────────────
    M = 1.0
    if 'Minyak Goreng Sawit Curah' in available_items:
        lp_problem += x['Minyak Goreng Sawit Curah']          <= M * pakai_minyak_curah,   'BigM_Minyak_Curah'
    if 'Minyak Goreng Sawit Kemasan Premium' in available_items:
        lp_problem += x['Minyak Goreng Sawit Kemasan Premium'] <= M * pakai_minyak_premium, 'BigM_Minyak_Premium'
    if 'Minyakita' in available_items:
        lp_problem += x['Minyakita']                           <= M * pakai_minyakita,      'BigM_Minyakita'

    if 'Beras Premium' in available_items:
        lp_problem += x['Beras Premium'] <= M * pakai_beras_premium, 'BigM_Beras_Premium'
    if 'Beras Medium' in available_items:
        lp_problem += x['Beras Medium']  <= M * pakai_beras_medium,  'BigM_Beras_Medium'

    # ── FIX: CONDITIONAL LOWER BOUND untuk Beras (via Big-M) ─────────────────
    # Jika biner=1 -> x >= 0.070 (minimal 70g porsi anak); jika biner=0 -> x >= 0 (bebas)
    if 'Beras Premium' in available_items:
        lp_problem += x['Beras Premium'] >= 0.070 * pakai_beras_premium, 'MinBeras_Premium'
    if 'Beras Medium' in available_items:
        lp_problem += x['Beras Medium']  >= 0.070 * pakai_beras_medium,  'MinBeras_Medium'

    lp_problem.solve(PULP_CBC_CMD(msg=False))

    if LpStatus[lp_problem.status] == 'Optimal':
        total_cost = value(lp_problem.objective)
        actual_kcal = sum(x[i].varValue * df_nutrition.loc[i, 'Energi'] for i in available_items)
        actual_protein = sum(x[i].varValue * df_nutrition.loc[i, 'Protein'] for i in available_items)
        return total_cost, actual_kcal, actual_protein, x
    return None, None, None, None

@st.cache_data
def get_trend_data(df_nutrition):
    df = pd.read_csv(DATA_CLEAN_PATH)
    all_commodities = df['variant_nama'].unique()
    available_items = [item for item in all_commodities if item in df_nutrition.index]
    
    hist_dates = sorted(df['tanggal'].unique())[-7:]
    trend_prices = {d: {} for d in hist_dates}
    
    last_date = pd.to_datetime(hist_dates[-1])
    future_dates = [(last_date + pd.Timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 8)]
    for d in future_dates:
        trend_prices[d] = {}
        
    for commodity in available_items:
        safe_filename = commodity.replace(" ", "_").replace("/", "_")
        model_path = os.path.join(MODEL_DIR, f"xgb_{safe_filename}.joblib")
        if not os.path.exists(model_path):
            continue
            
        model = joblib.load(model_path)
        df_model = df[df['variant_nama'] == commodity].sort_values('tanggal')
        
        for d in hist_dates:
            val = df_model[df_model['tanggal'] == d]['harga']
            if not val.empty:
                trend_prices[d][commodity] = float(val.iloc[0])
            else:
                trend_prices[d][commodity] = float(df_model['harga'].iloc[-1])
                
        features = ['day', 'day_of_week', 'is_weekend', 'price_lag_1', 'price_lag_2', 'price_lag_3', 'rolling_mean_7d']
        history_prices = df_model['harga'].tolist()[-7:]
        
        for i, f_date in enumerate(future_dates):
            f_dt = pd.to_datetime(f_date)
            X_pred = pd.DataFrame([[f_dt.day, f_dt.dayofweek, 1 if f_dt.dayofweek >= 5 else 0, 
                                    history_prices[-1], history_prices[-2], history_prices[-3], 
                                    sum(history_prices[-7:]) / 7.0]], columns=features)
            pred_price = model.predict(X_pred)[0]
            trend_prices[f_date][commodity] = float(pred_price)
            history_prices.append(float(pred_price))
            
    trend_results = []
    last_hist_date = hist_dates[-1]
    for d in hist_dates + future_dates:
        prices = trend_prices[d]
        if not prices: continue
        
        for commodity, price in prices.items():
            trend_results.append({
                'Tanggal': d,
                'Komoditas': commodity,
                'Harga': price,
                'Tipe': 'Historis' if d in hist_dates else 'Prediksi'
            })
            if d == last_hist_date:
                trend_results.append({
                    'Tanggal': d,
                    'Komoditas': commodity,
                    'Harga': price,
                    'Tipe': 'Prediksi'
                })
    return pd.DataFrame(trend_results)

predicted_prices_tomorrow = predict_prices()
df_nutrition = load_nutrition_data()
available_items = [item for item in predicted_prices_tomorrow.keys() if item in df_nutrition.index]

with st.sidebar:
    st.markdown("**Konfigurasi Target**")
    st.caption("Sesuaikan kebutuhan minimum gizi per porsi makan siang anak (⅓ kebutuhan harian):")
    target_kkal = st.slider("Target Energi (Kcal)", 400, 1000, 700, step=50)
    target_protein = st.slider("Target Protein (gram)", 10, 40, 20, step=1)
    
    st.markdown("---")
    st.markdown("**Konfigurasi Skala Program**")
    st.caption("Digunakan untuk proyeksi total anggaran:")
    jumlah_anak = st.number_input("Target Porsi Harian", min_value=1, value=82900000, step=1000000)
    hari_aktif_bulan = st.number_input("Hari Aktif per Bulan", min_value=1, max_value=31, value=22, step=1)
    hari_aktif_tahun = hari_aktif_bulan * 12
    
    st.markdown("---")
    st.caption("Data harga pasar diprediksi menggunakan model XGBoost untuk mendapatkan estimasi harga terbaru.")

if st.button("Generate Rekomendasi Menu", use_container_width=True, type="primary"):
    st.session_state.generate_clicked = True

if st.session_state.get('generate_clicked', False):
    with st.spinner("Menghitung kombinasi menu optimal dan tren harga..."):
        total_cost, actual_kcal, actual_protein, x_vars = calculate_optimal_budget(
            predicted_prices_tomorrow, target_kkal, target_protein, df_nutrition, available_items
        )
        
        if total_cost is not None:
            pagu_standar = 10000
            selisih_pagu = pagu_standar - total_cost
            delta_pct = (selisih_pagu / pagu_standar) * 100
            
            st.markdown('<div class="section-header">Hasil Optimasi Besok</div>', unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                with st.container(border=True):
                    st.metric(label="Total Biaya / Anak", value=f"Rp {total_cost:,.0f}", delta=f"{-delta_pct:.1f}% vs Pagu Awal")
            with col2:
                with st.container(border=True):
                    st.metric(label="Penghematan Anggaran", value=f"Rp {selisih_pagu:,.0f}", delta=f"{delta_pct:.1f}% Efisiensi")
            with col3:
                with st.container(border=True):
                    st.metric(label="Total Energi (Kcal)", value=f"{target_kkal:,.0f}", delta="Sesuai Target", delta_color="off")
            with col4:
                with st.container(border=True):
                    st.metric(label="Total Protein (g)", value=f"{target_protein:,.1f}", delta="Sesuai Target", delta_color="off")
            
            # Proyeksi Skalabilitas
            total_biaya_harian = total_cost * jumlah_anak
            total_biaya_bulanan = total_biaya_harian * hari_aktif_bulan
            total_biaya_tahunan = total_biaya_harian * hari_aktif_tahun
            
            pagu_harian = pagu_standar * jumlah_anak
            pagu_bulanan = pagu_harian * hari_aktif_bulan
            pagu_tahunan = pagu_harian * hari_aktif_tahun
            
            penghematan_harian = selisih_pagu * jumlah_anak
            penghematan_bulanan = penghematan_harian * hari_aktif_bulan
            penghematan_tahunan = penghematan_harian * hari_aktif_tahun
            
            st.markdown(f'<div class="section-header">Proyeksi Penghematan (Target: {jumlah_anak:,} Porsi/Hari)</div>', unsafe_allow_html=True)
            
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                with st.container(border=True):
                    st.markdown("**Proyeksi Harian**")
                    st.metric(label="Anggaran Pagu Standar", value=format_rupiah(pagu_harian))
                    st.metric(label="Anggaran NutriCost AI", value=format_rupiah(total_biaya_harian), delta=f"Hemat {format_rupiah(penghematan_harian)} ({delta_pct:.1f}%)")
            with col_p2:
                with st.container(border=True):
                    st.markdown(f"**Proyeksi Bulanan ({hari_aktif_bulan} Hari)**")
                    st.metric(label="Anggaran Pagu Standar", value=format_rupiah(pagu_bulanan))
                    st.metric(label="Anggaran NutriCost AI", value=format_rupiah(total_biaya_bulanan), delta=f"Hemat {format_rupiah(penghematan_bulanan)} ({delta_pct:.1f}%)")
            with col_p3:
                with st.container(border=True):
                    st.markdown(f"**Proyeksi Tahunan ({hari_aktif_tahun} Hari)**")
                    st.metric(label="Anggaran Pagu Standar", value=format_rupiah(pagu_tahunan))
                    st.metric(label="Anggaran NutriCost AI", value=format_rupiah(total_biaya_tahunan), delta=f"Hemat {format_rupiah(penghematan_tahunan)} ({delta_pct:.1f}%)")
            
            st.info(" **Catatan:** Anggaran yang ditampilkan di atas murni merupakan estimasi biaya bahan baku mentah (makanan pokok, lauk, dan bumbu). Perhitungan ini belum termasuk biaya operasional seperti logistik, tenaga masak, distribusi, gas, dan kemasan.")
            
            st.markdown('<div class="section-header">Tren Harga Per Bahan Pokok (7 Hari Terakhir & 7 Hari Kedepan)</div>', unsafe_allow_html=True)
            df_trend = get_trend_data(df_nutrition)
            
            all_trend_commodities = sorted(df_trend['Komoditas'].unique())
            default_commodity = [all_trend_commodities[0]] if all_trend_commodities else []
            
            selected_commodities = st.multiselect(
                "Pilih Komoditas untuk Ditampilkan:",
                options=all_trend_commodities,
                default=default_commodity
            )
            
            df_trend_filtered = df_trend[df_trend['Komoditas'].isin(selected_commodities)] if selected_commodities else df_trend.iloc[0:0]
            
            fig = px.line(df_trend_filtered, x='Tanggal', y='Harga', color='Komoditas', line_dash='Tipe', markers=True,
                          title="Pergerakan Harga Masing-masing Bahan Pokok")
            fig.update_layout(yaxis_title='Harga (Rp)', xaxis_title='Tanggal',
                              hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0))
            fig.update_traces(line=dict(width=2))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('<div class="section-header">Rekomendasi Bahan Baku per Porsi Besok</div>', unsafe_allow_html=True)
            
            resep_items = []
            estimasi_biaya = []
            gramasi = []
            
            for item in available_items:
                qty_kg = x_vars[item].varValue
                if qty_kg > 0.001:
                    cost_item = qty_kg * predicted_prices_tomorrow[item]
                    resep_items.append(item)
                    gramasi.append(f"{qty_kg * 1000:.0f} g")
                    estimasi_biaya.append(f"Rp {cost_item:,.0f}")
                    
            data_resep = {
                "Komoditas": resep_items,
                "Kuantitas": gramasi,
                "Estimasi Biaya": estimasi_biaya
            }
            
            df_resep = pd.DataFrame(data_resep)
            html_table = df_resep.to_html(index=False, classes='styled-table', escape=False)
            st.markdown(html_table, unsafe_allow_html=True)
            
        else:
            st.error("Error: Tidak dapat menemukan menu optimal dengan batasan gizi yang diberikan.")