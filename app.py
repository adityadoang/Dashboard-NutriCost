from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pandas as pd
import numpy as np
import pulp
import os
import joblib

app = FastAPI(title="NutriCost Optimizer API")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load Data and Models globally
MODEL_DIR = 'trained_models'
df = None
metadata_komoditas = None
df_nutrition = None
features = []

# Global cache for predicted prices to avoid re-predicting every time
PREDICTED_PRICES = {}

def load_data_and_predict():
    global df, metadata_komoditas, df_nutrition, features, PREDICTED_PRICES
    
    try:
        df = pd.read_csv('dataset_transformed.csv')
        metadata_komoditas = joblib.load(os.path.join(MODEL_DIR, 'metadata_komoditas.pkl'))
        
        exclude_cols = ['Unnamed: 0', 'variant_id', 'variant_nama', 'satuan_display', 'tanggal', 'harga', 'harga_final', 'diff_order']
        features = [col for col in df.columns if col not in exclude_cols]
        
        df_nutrition = pd.read_csv('dataset_gizi.csv')
        df_nutrition.set_index('KOMODITAS', inplace=True)
        
        all_commodities = df['variant_nama'].unique()
        
        for commodity in all_commodities:
            safe_filename = commodity.replace(' ', '_').replace('/', '_')
            model_path = os.path.join(MODEL_DIR, f'xgb_model_{safe_filename}.pkl')
            
            if os.path.exists(model_path):
                model = joblib.load(model_path)
                df_var = df[df['variant_nama'] == commodity].sort_values('tanggal').copy()
                diff_val = metadata_komoditas.get(commodity, 0)
                
                df_var['harga_shift_1'] = df_var['harga'].shift(1)
                df_var['harga_shift_2'] = df_var['harga'].shift(2)
                df_var['sma_7_hari'] = df_var['harga_shift_1'].rolling(window=7).mean()
                
                latest_features = df_var[features].iloc[-1:].copy()
                y_pred_diff = model.predict(latest_features)[0]
                
                last_row = df_var.iloc[-1]
                harga_shift_1 = last_row['harga']
                harga_shift_2 = df_var['harga'].iloc[-2] if len(df_var) >= 2 else harga_shift_1
                
                if diff_val == 0:
                    tomorrow_price = y_pred_diff
                elif diff_val == 1:
                    tomorrow_price = harga_shift_1 + y_pred_diff
                elif diff_val == 2:
                    tomorrow_price = harga_shift_1 + (harga_shift_1 - harga_shift_2) + y_pred_diff
                else:
                    tomorrow_price = y_pred_diff
                
                tomorrow_price = max(0, float(tomorrow_price))
                last_7 = df_var.tail(7)
                hist_dates = last_7['tanggal'].tolist()
                hist_prices = last_7['harga'].tolist()
                
                try:
                    last_date_obj = pd.to_datetime(hist_dates[-1])
                    pred_date_obj = last_date_obj + pd.Timedelta(days=1)
                    pred_date_str = pred_date_obj.strftime('%Y-%m-%d')
                except:
                    pred_date_str = "H+1"
                
                PREDICTED_PRICES[commodity] = {
                    "historical_dates": hist_dates,
                    "historical_prices": hist_prices,
                    "predicted_date": pred_date_str,
                    "predicted_price": tomorrow_price
                }
                
        print("Model loaded and prices predicted successfully.")
    except Exception as e:
        print(f"Error loading data or predicting: {e}")

# Run once at startup
load_data_and_predict()

class OptimizeRequest(BaseModel):
    target_kcal: float = 700.0
    target_protein: float = 20.0

@app.get("/")
def read_root():
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse("static/index.html", headers=headers)

@app.get("/api/prices")
def get_prices():
    if not PREDICTED_PRICES:
        raise HTTPException(status_code=500, detail="Prices not available.")
    return {"prices": PREDICTED_PRICES}

@app.post("/api/optimize")
def optimize_diet(req: OptimizeRequest):
    if not PREDICTED_PRICES or df_nutrition is None:
        raise HTTPException(status_code=500, detail="Data not loaded.")
        
    available_items = [item for item in PREDICTED_PRICES.keys() if item in df_nutrition.index]
    
    lp_problem = pulp.LpProblem("NutriCost_Diet_Optimization", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("qty_kg", available_items, lowBound=0, cat='Continuous')
    
    pakai_minyak_curah   = pulp.LpVariable('Pakai_Minyak_Curah',   cat='Binary')
    pakai_minyak_premium = pulp.LpVariable('Pakai_Minyak_Premium', cat='Binary')
    pakai_minyakita      = pulp.LpVariable('Pakai_Minyakita',      cat='Binary')
    
    pakai_beras_premium  = pulp.LpVariable('Pakai_Beras_Premium',  cat='Binary')
    pakai_beras_medium   = pulp.LpVariable('Pakai_Beras_Medium',   cat='Binary')

    # FUNGSI OBJEKTIF
    lp_problem += pulp.lpSum([PREDICTED_PRICES[i]["predicted_price"] * x[i] for i in available_items]), "Total_Cost"
    
    # KENDALA GIZI DINAMIS (Berdasarkan Input User)
    lp_problem += pulp.lpSum([df_nutrition.loc[i, 'Energi'] * x[i] for i in available_items]) >= req.target_kcal, "Min_Energy"
    lp_problem += pulp.lpSum([df_nutrition.loc[i, 'Protein'] * x[i] for i in available_items]) >= req.target_protein, "Min_Protein"
    


    # KENDALA LOGIKA MANUSIA
    for i in available_items:
        if 'Beras' in i:
            lp_problem += x[i] <= 0.080
        elif 'Terigu' in i:
            lp_problem += x[i] <= 0.015
        elif 'Kedelai' in i:
            lp_problem += x[i] >= 0.020
            lp_problem += x[i] <= 0.040
        elif 'Ayam' in i or 'Telur' in i:
            lp_problem += x[i] <= 0.060
        elif 'Sapi' in i:
            lp_problem += x[i] <= 0.050
        elif 'Gula' in i:
            lp_problem += x[i] <= 0.008
        elif 'Minyak' in i:
            lp_problem += x[i] <= 0.010
        elif 'Bawang' in i:
            lp_problem += x[i] >= 0.002
            lp_problem += x[i] <= 0.006
        elif 'Cabai' in i:
            lp_problem += x[i] <= 0.002

    protein_hewani_items = [i for i in available_items if 'Ayam' in i or 'Sapi' in i or 'Telur' in i]
    if protein_hewani_items:
        lp_problem += pulp.lpSum([x[i] for i in protein_hewani_items]) >= 0.030, "Min_Protein_Hewani"

    lp_problem += pakai_minyak_curah + pakai_minyak_premium + pakai_minyakita <= 1, 'Pilih_Maks_1_Minyak'
    lp_problem += pakai_beras_premium + pakai_beras_medium <= 1, 'Pilih_Maks_1_Beras'

    if 'Minyak Goreng Sawit Curah' in available_items:
        lp_problem += x['Minyak Goreng Sawit Curah']           <= 0.010 * pakai_minyak_curah
    if 'Minyak Goreng Sawit Kemasan Premium' in available_items:
        lp_problem += x['Minyak Goreng Sawit Kemasan Premium'] <= 0.010 * pakai_minyak_premium
    if 'Minyakita' in available_items:
        lp_problem += x['Minyakita']                           <= 0.010 * pakai_minyakita

    if 'Beras Premium' in available_items:
        lp_problem += x['Beras Premium'] <= 0.080 * pakai_beras_premium
    if 'Beras Medium' in available_items:
        lp_problem += x['Beras Medium']  <= 0.080 * pakai_beras_medium

    if 'Beras Premium' in available_items:
        lp_problem += x['Beras Premium'] >= 0.050 * pakai_beras_premium
    if 'Beras Medium' in available_items:
        lp_problem += x['Beras Medium']  >= 0.050 * pakai_beras_medium

    if 'Minyak Goreng Sawit Curah' in available_items:
        lp_problem += x['Minyak Goreng Sawit Curah']           >= 0.002 * pakai_minyak_curah
    if 'Minyak Goreng Sawit Kemasan Premium' in available_items:
        lp_problem += x['Minyak Goreng Sawit Kemasan Premium'] >= 0.002 * pakai_minyak_premium
    if 'Minyakita' in available_items:
        lp_problem += x['Minyakita']                           >= 0.002 * pakai_minyakita

    lp_problem.solve()
    
    if pulp.LpStatus[lp_problem.status] == 'Optimal':
        total_cost = pulp.value(lp_problem.objective)
        
        recommendations = []
        total_kcal = 0
        total_protein = 0
        
        # Sector Mapping for Financial Inclusion
        SECTORS = {
            'Beras SPHP Bulog': 'Petani Padi (UMKM)',
            'Beras Medium': 'Petani Padi (UMKM)',
            'Beras Premium': 'Petani Padi (UMKM)',
            'Daging Ayam Ras': 'Peternak Unggas (UMKM)',
            'Telur Ayam Ras': 'Peternak Unggas (UMKM)',
            'Daging Sapi Paha Belakang': 'Peternak Sapi (UMKM)',
            'Cabai Merah Keriting': 'Petani Hortikultura (UMKM)',
            'Cabai Merah Besar': 'Petani Hortikultura (UMKM)',
            'Cabai Rawit Merah': 'Petani Hortikultura (UMKM)',
            'Bawang Merah': 'Petani Hortikultura (UMKM)',
            'Bawang Putih Honan': 'Petani Hortikultura (UMKM)',
            'Kedelai Impor': 'Petani Palawija (UMKM)',
            'Gula Pasir Curah': 'Industri Pengolahan',
            'Minyak Goreng Sawit Curah': 'Industri Pengolahan',
            'Minyak Goreng Sawit Kemasan Premium': 'Industri Pengolahan',
            'Minyakita': 'Industri Pengolahan',
            'Tepung Terigu': 'Industri Pengolahan'
        }
        
        financial_flow = {}
        
        for item in available_items:
            qty_kg = x[item].varValue
            if qty_kg is not None and qty_kg > 0.001:
                qty_grams = qty_kg * 1000
                kcal_supplied = qty_kg * df_nutrition.loc[item, 'Energi']
                protein_supplied = qty_kg * df_nutrition.loc[item, 'Protein']
                cost_item = qty_kg * PREDICTED_PRICES[item]["predicted_price"]
                
                sector = SECTORS.get(item, 'Lainnya')
                financial_flow[sector] = financial_flow.get(sector, 0) + cost_item
                
                recommendations.append({
                    "item": item,
                    "qty_grams": round(qty_grams),
                    "cost": round(cost_item),
                    "kcal": round(kcal_supplied, 1),
                    "protein": round(protein_supplied, 1)
                })
                
                total_kcal += kcal_supplied
                total_protein += protein_supplied
                
        return {
            "status": "success",
            "total_cost": round(total_cost, 2),
            "total_kcal": round(total_kcal, 1),
            "total_protein": round(total_protein, 1),
            "financial_flow": financial_flow,
            "recommendations": recommendations
        }
    else:
        return {
            "status": "error",
            "message": f"Tidak dapat menemukan menu optimal (Status: {pulp.LpStatus[lp_problem.status]}). Coba ubah target gizi."
        }
