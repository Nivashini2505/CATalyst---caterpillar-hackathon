"""
Train demand-forecasting model.
Input:  ml/data/demand_summary.csv (weekly bookings per country x machine_type)
Output: ml/artifacts/demand_model.pkl + demand_metrics.json

Model: GradientBoostingRegressor (predicts weekly bookings).
Features: month, iso_week, seasonality_index (from generator's real
patterns), year offset, country + machine_type (one-hot), lagged bookings
(prev 1w, prev 4w), and 4-week rolling mean.

We hold out the last 12 weeks per (country, machine_type) as test set —
that's a real time-series-style evaluation, not a shuffled split.
"""

from __future__ import annotations
import json, joblib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ART = HERE / "artifacts"
ART.mkdir(exist_ok=True)

print("Loading demand_summary.csv...")
df = pd.read_csv(DATA / "demand_summary.csv")
df["week_start"] = pd.to_datetime(df["week_start"])
df = df.sort_values(["country", "machine_type", "week_start"]).reset_index(drop=True)

# Lag features per (country, machine_type)
def add_lags(g):
    g = g.copy()
    g["lag_1w"] = g["bookings"].shift(1).fillna(0)
    g["lag_4w"] = g["bookings"].shift(4).fillna(0)
    g["roll_4w"] = g["bookings"].shift(1).rolling(4, min_periods=1).mean().fillna(0)
    return g

df = df.groupby(["country","machine_type"], group_keys=False).apply(add_lags)

FEATURES_NUM = ["month","iso_week","seasonality_index","lag_1w","lag_4w","roll_4w","year"]
FEATURES_CAT = ["country","machine_type"]
TARGET = "bookings"

# Time-based split: last 12 weeks per group -> test set
cutoff = df["week_start"].max() - pd.Timedelta(weeks=12)
train = df[df["week_start"] <= cutoff].copy()
test  = df[df["week_start"] >  cutoff].copy()

X_train = pd.get_dummies(train[FEATURES_NUM + FEATURES_CAT], columns=FEATURES_CAT, drop_first=False)
X_test  = pd.get_dummies(test [FEATURES_NUM + FEATURES_CAT], columns=FEATURES_CAT, drop_first=False)
# Align columns
missing = set(X_train.columns) - set(X_test.columns)
for m in missing: X_test[m] = 0
X_test = X_test[X_train.columns]
y_train, y_test = train[TARGET], test[TARGET]
print(f"train rows: {len(X_train)}, test rows: {len(X_test)}, features: {X_train.shape[1]}")

print("Training GradientBoostingRegressor...")
model = GradientBoostingRegressor(
    n_estimators=300, max_depth=5, learning_rate=0.08,
    subsample=0.9, random_state=42
)
model.fit(X_train, y_train)
pred = np.clip(model.predict(X_test), 0, None)

mae = mean_absolute_error(y_test, pred)
mape = mean_absolute_percentage_error(np.maximum(y_test, 1), pred)
r2 = r2_score(y_test, pred)
metrics = {
    "model": "GradientBoostingRegressor",
    "train_rows": int(len(X_train)),
    "test_rows": int(len(X_test)),
    "MAE": round(float(mae), 3),
    "MAPE_pct": round(float(mape) * 100, 2),
    "R2": round(float(r2), 4),
    "features_used": list(X_train.columns),
    "target": TARGET,
}
print("Metrics:", json.dumps({k:v for k,v in metrics.items() if k != "features_used"}, indent=2))

# Feature importance top 15
fi = pd.DataFrame({"feature": X_train.columns, "importance": model.feature_importances_}) \
        .sort_values("importance", ascending=False).head(15)
print("\nTop features:")
print(fi.to_string(index=False))
metrics["top_features"] = fi.to_dict("records")

joblib.dump({"model": model, "columns": list(X_train.columns)}, ART / "demand_model.pkl", compress=3)
with open(ART / "demand_metrics.json", "w") as f: json.dump(metrics, f, indent=2)
print("\nSaved artifacts to", ART)
