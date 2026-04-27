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

def calculate_optimal_budget(prices_dict, target_kkal, target_protein, df_nutrition, available_items):
    lp_problem = LpProblem("NutriCost_Diet_Optimization", LpMinimize)
    x = LpVariable.dicts("qty_kg", available_items, lowBound=0, cat='Continuous')
    
    # 1. FUNGSI OBJEKTIF
    lp_problem += lpSum([prices_dict[i] * x[i] for i in available_items]), "Total_Cost"
    
    # 2. KENDALA GIZI
    lp_problem += lpSum([df_nutrition.loc[i, 'Energi'] * x[i] for i in available_items]) >= target_kkal, "Min_Energy"
    lp_problem += lpSum([df_nutrition.loc[i, 'Protein'] * x[i] for i in available_items]) >= target_protein, "Min_Protein"
    
    # 3. KENDALA LOGIKA MANUSIA
    for i in available_items:
        if 'Beras' in i:
            lp_problem += x[i] >= 0.100
            lp_problem += x[i] <= 0.250
        elif 'Terigu' in i:
            lp_problem += x[i] <= 0.050
        elif 'Gula' in i:
            lp_problem += x[i] <= 0.020
        elif 'Minyak' in i:
            lp_problem += x[i] <= 0.030
        elif 'Cabai' in i or 'Bawang' in i:
            lp_problem += x[i] <= 0.010
            
    protein_hewani_items = [i for i in available_items if 'Ayam' in i or 'Sapi' in i or 'Telur' in i]
    if protein_hewani_items:
        lp_problem += lpSum([x[i] for i in protein_hewani_items]) >= 0.050
        
    lp_problem.solve(PULP_CBC_CMD(msg=False))
    
    if LpStatus[lp_problem.status] == 'Optimal':
        total_cost = value(lp_problem.objective)
        actual_kcal = sum(x[i].varValue * df_nutrition.loc[i, 'Energi'] for i in available_items)
        actual_protein = sum(x[i].varValue * df_nutrition.loc[i, 'Protein'] for i in available_items)
        return total_cost, actual_kcal, actual_protein, x
    return None, None, None, None

@st.cache_data
def get_trend_data(target_kkal, target_protein, df_nutrition):
    df = pd.read_csv(DATA_CLEAN_PATH)
    all_commodities = df['variant_nama'].unique()
    available_items = [item for item in all_commodities if item in df_nutrition.index]
    
    last_5_dates = sorted(df['tanggal'].unique())[-5:]
    trend_prices = {d: {} for d in last_5_dates}
    
    last_date = pd.to_datetime(last_5_dates[-1])
    future_dates = [(last_date + pd.Timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 6)]
    for d in future_dates:
        trend_prices[d] = {}
        
    for commodity in available_items:
        safe_filename = commodity.replace(" ", "_").replace("/", "_")
        model_path = os.path.join(MODEL_DIR, f"xgb_{safe_filename}.joblib")
        if not os.path.exists(model_path):
            continue
            
        model = joblib.load(model_path)
        df_model = df[df['variant_nama'] == commodity].sort_values('tanggal')
        
        for d in last_5_dates:
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
    last_hist_date = last_5_dates[-1]
    for d in last_5_dates + future_dates:
        prices = trend_prices[d]
        if not prices: continue
        valid_items = list(prices.keys())
        cost, _, _, _ = calculate_optimal_budget(prices, target_kkal, target_protein, df_nutrition, valid_items)
        if cost is not None:
            trend_results.append({
                'Tanggal': d,
                'Biaya': cost,
                'Tipe': 'Historis' if d in last_5_dates else 'Prediksi'
            })
            if d == last_hist_date:
                trend_results.append({
                    'Tanggal': d,
                    'Biaya': cost,
                    'Tipe': 'Prediksi'
                })
    return pd.DataFrame(trend_results)

predicted_prices_tomorrow = predict_prices()
df_nutrition = load_nutrition_data()
available_items = [item for item in predicted_prices_tomorrow.keys() if item in df_nutrition.index]

with st.sidebar:
    st.markdown("**Konfigurasi Target**")
    st.caption("Sesuaikan kebutuhan minimum gizi harian per anak:")
    target_kkal = st.slider("Target Energi (Kcal)", 1500, 2500, 2000, step=50)
    target_protein = st.slider("Target Protein (gram)", 40, 70, 50, step=1)
    
    st.markdown("---")
    st.caption("Data harga pasar diprediksi menggunakan model XGBoost untuk mendapatkan estimasi harga terbaru.")

if st.button("Generate Rekomendasi Menu", use_container_width=True, type="primary"):
    with st.spinner("Menghitung kombinasi menu optimal dan tren harga..."):
        total_cost, actual_kcal, actual_protein, x_vars = calculate_optimal_budget(
            predicted_prices_tomorrow, target_kkal, target_protein, df_nutrition, available_items
        )
        
        if total_cost is not None:
            pagu_standar = 15000
            delta_pct = (total_cost - pagu_standar) / pagu_standar * 100
            
            st.markdown('<div class="section-header">Hasil Optimasi Besok</div>', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                with st.container(border=True):
                    st.metric(label="Total Biaya per Anak", value=f"Rp {total_cost:,.2f}", delta=f"{delta_pct:.1f}% vs Pagu Standar")
            with col2:
                with st.container(border=True):
                    st.metric(label="Total Energi (Kcal)", value=f"{actual_kcal:,.1f}", delta=f"{actual_kcal - target_kkal:,.1f} Kcal surplus")
            with col3:
                with st.container(border=True):
                    st.metric(label="Total Protein (gram)", value=f"{actual_protein:,.1f}", delta=f"{actual_protein - target_protein:,.1f}g surplus")
            
            st.markdown('<div class="section-header">Tren Anggaran (5 Hari Terakhir & 5 Hari Kedepan)</div>', unsafe_allow_html=True)
            df_trend = get_trend_data(target_kkal, target_protein, df_nutrition)
            
            fig = px.line(df_trend, x='Tanggal', y='Biaya', color='Tipe', markers=True,
                          color_discrete_map={'Historis': '#3b82f6', 'Prediksi': '#ef4444'},
                          title="Pergerakan Biaya Optimal per Anak")
            fig.update_layout(yaxis_title='Biaya (Rp)', xaxis_title='Tanggal',
                              yaxis=dict(range=[0, 10000]),
                              hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0))
            fig.update_traces(line=dict(width=3))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('<div class="section-header">Rincian Bahan Baku Besok</div>', unsafe_allow_html=True)
            
            resep_items = []
            gramasi = []
            estimasi_biaya = []
            
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