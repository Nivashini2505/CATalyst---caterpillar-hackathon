import axios from 'axios';

// All calls go to the existing FastAPI backend (proxied /api -> :8000).
const api = axios.create({ baseURL: '/api/v1', timeout: 30000 });

// ---------- Types ----------
export interface CountrySeriesRow {
  machineType: string; category: string; forecastNextWeek: number;
  recentAvg: number; delta: number; trend: 'up' | 'down' | 'flat'; demandLevel: string;
}
export interface AnomalyEvent {
  id: string; assetId: string; equipment: string; equipmentType: string;
  anomalyType: string; anomalyLabel: string; reason: string;
  severity: 'critical' | 'high' | 'medium' | 'low'; confidence: number;
  estimatedDailyCost: number; site: string; detectedOn: string;
  engineHoursToday: number; idleHoursToday: number; hasOperator: boolean; gpsStatus: string;
}
export interface AnomalySummary {
  totalAnomalies: number;
  bySeverity: { critical: number; high: number; medium: number; low: number };
  byType: { type: string; count: number }[];
  estimatedDailyExposure: number;
}
export interface Equipment {
  id: string; name: string; model: string; category: string; image: string;
  site: string; operator: string; health: number; engineHours: number;
  idleHours: number; rentalRemainingDays: number; status: string; riskScore: number; isLive?: boolean;
}
export interface MaintenancePrediction {
  assetId: string; health: number; riskScore: number; maintenanceProbability: number;
  maintenanceWithin30d: boolean; reason: string; topFactor?: string;
  lifeUsedPct?: number; vibration?: number; oilTemp?: number;
}
export interface MaintenanceForecast {
  assetId: string;
  prediction: MaintenancePrediction;
  timeline: { date: string; event: string; status: string; confidence?: number }[];
}

// ---------- Demand Forecasting ----------
export const getTrends = () => api.get('/analytics/trends').then((r) => r.data);
export const getForecastCountries = () =>
  api.get('/analytics/forecast/countries').then((r) => r.data.countries as string[]);
export const getForecastByCountry = (country: string) =>
  api.get(`/analytics/forecast/country/${encodeURIComponent(country)}`).then((r) => r.data as {
    country: string; series: CountrySeriesRow[];
  });
export const getForecastComparison = (machineType?: string) =>
  api.get('/analytics/forecast/comparison', { params: machineType ? { machine_type: machineType } : {} })
    .then((r) => r.data as { machineType: string; data: { country: string; forecast: number }[] });

// ---------- Anomaly Detection ----------
export const getAnomalies = (limit = 50, minSeverity?: string) =>
  api.get('/ai/anomalies', { params: { limit, ...(minSeverity ? { min_severity: minSeverity } : {}) } })
    .then((r) => r.data as AnomalyEvent[]);
export const getAnomalySummary = () =>
  api.get('/ai/anomalies/summary').then((r) => r.data as AnomalySummary);

// ---------- Predictive Maintenance ----------
export const getEquipment = () => api.get('/equipment').then((r) => r.data as Equipment[]);
export const getMaintenanceForecast = (assetId: string) =>
  api.get(`/equipment/${encodeURIComponent(assetId)}/maintenance-forecast`).then((r) => r.data as MaintenanceForecast);

// ---------- Model metrics (confidence / performance) ----------
export const getModelMetrics = () => api.get('/ai/model-metrics').then((r) => r.data);
