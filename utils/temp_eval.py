import pandas as pd
import numpy as np
import joblib
import os
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error

df = pd.read_csv('dataset_clean.csv')
all_commodities = df['variant_nama'].unique()
MODEL_DIR = 'trained_models'
validation_results = []

for commodity in all_commodities:
    safe_filename = commodity.replace(" ", "_").replace("/", "_")
    model_path = os.path.join(MODEL_DIR, f"xgb_{safe_filename}.joblib")
    
    if os.path.exists(model_path):
        model = joblib.load(model_path)
        df_model = df[df['variant_nama'] == commodity].sort_values('tanggal').reset_index(drop=True)
        features = ['day', 'day_of_week', 'is_weekend', 'price_lag_1', 'price_lag_2', 'price_lag_3', 'rolling_mean_7d']
        
        X = df_model[features]
        y = df_model['harga']
        split_index = int(len(df_model) * 0.8)
        X_test, y_test = X.iloc[split_index:], y.iloc[split_index:]
        
        predictions = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, predictions))
        mape = mean_absolute_percentage_error(y_test, predictions) * 100
        
        importances = model.feature_importances_
        top_feature_index = np.argmax(importances)
        top_feature = features[top_feature_index]
        
        validation_results.append({
            'Commodity': commodity,
            'MAPE (%)': round(mape, 2),
            'RMSE (IDR)': round(rmse, 2),
            'Top Feature': top_feature
        })

df_report = pd.DataFrame(validation_results)
df_report = df_report.sort_values(by='MAPE (%)').reset_index(drop=True)
print(df_report.to_markdown(index=False))
