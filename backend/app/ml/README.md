# ML Layer — Dealer Dashboard AI

Three trained models power the dealer dashboard's AI features. Everything here
is **self-contained** — models + a compact serving snapshot ship in this folder,
so no database or external service is required for the AI endpoints to work.

## What's here

```
backend/app/ml/
├── inference.py            # the only file the API imports — loads models once,
│                           #   exposes predict_* / detect_* functions
├── artifacts/              # trained models (joblib-compressed) + metrics JSON
│   ├── demand_model.pkl            GradientBoostingRegressor
│   ├── anomaly_model.pkl           IsolationForest + RandomForest + type classifier
│   ├── maintenance_model.pkl       RandomForest (30-day risk) + GB regressor (health)
│   └── *_metrics.json              held-out evaluation metrics
└── serving/               # compact snapshot the models score against at runtime
    ├── machines.csv               550 assets
    ├── demand_summary.csv         weekly bookings history (forecast input)
    ├── telemetry_latest.csv       latest row per asset (fleet health)
    ├── telemetry_recent.csv       last 45 days (anomaly feed)
    └── sites.csv / customers.csv / operators.csv
```

## The three models

| Model | Task | Algorithm | Held-out metric |
|-------|------|-----------|-----------------|
| Demand forecast | next-week bookings per country × equipment type | GradientBoostingRegressor | R² 0.51, MAE 1.5 |
| Anomaly detection | flag + classify suspicious telemetry | IsolationForest + RandomForest hybrid | AUC 0.9999, type-acc 99.7% |
| Predictive maintenance | 30-day service risk + health score | RandomForest + GradientBoosting | AUC 0.95 |

### Anomaly signals (incl. the ones Caterpillar highlighted)
- **Unauthorized use** — engine hours > 0 while operator ID is empty
- **Unaccounted asset** — engine hours 0 + no operator for several days while checked out
- Geofence breach, fuel anomaly (2×+ expected burn), impossible hours (>24h/day),
  GPS jump, sensor failure, excessive idle.

> The anomaly model **never** sees order size / bulk flag / customer, so a
> legitimate large mining rental is never flagged just for being big.

## API endpoints wired to these models

| Endpoint | Model | UI surface |
|----------|-------|-----------|
| `GET /api/v1/analytics/trends` | demand | Mission Control + Forecasting demand chart |
| `GET /api/v1/analytics/forecast/countries` | demand | country selector |
| `GET /api/v1/analytics/forecast/country/{country}` | demand | per-country outlook |
| `GET /api/v1/analytics/forecast/comparison` | demand | cross-country bar chart |
| `GET /api/v1/ai/recommendations` | anomaly | Decision Center cards |
| `GET /api/v1/ai/anomalies` | anomaly | Anomaly Monitor feed |
| `GET /api/v1/ai/anomalies/summary` | anomaly | severity band + $ exposure |
| `GET /api/v1/ai/model-metrics` | all | model-performance panel |
| `GET /api/v1/equipment` | maintenance | Fleet health/risk |
| `GET /api/v1/equipment/{id}/maintenance-forecast` | maintenance | Equipment Details timeline |

All endpoints degrade gracefully: if an artifact is missing they return a
deterministic fallback instead of erroring.

## Setup

```bash
cd backend
pip install -r requirements.txt   # adds scikit-learn, pandas, numpy, joblib
uvicorn app.main:app --reload
```

Models are loaded and the fleet health cache is warmed on startup (see
`app/main.py` lifespan) so the first dashboard request is instant.

## Regenerating (optional)

The dataset generator + training scripts live in the repo root `ml/` folder
(one level above this backend). To rebuild everything:

```bash
python ml/generate_dataset.py          # regenerate synthetic CSVs
python ml/train_demand_forecast.py
python ml/train_anomaly.py
python ml/train_maintenance.py
python ml/build_serving_snapshot.py    # copies artifacts + snapshot into backend/app/ml
```
