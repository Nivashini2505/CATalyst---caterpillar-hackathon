import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchEquipment = async () => {
  const response = await api.get('/equipment');
  return response.data;
};

export const fetchKPIs = async () => {
  const response = await api.get('/analytics/kpis');
  return response.data;
};

export const fetchRecommendations = async () => {
  const response = await api.get('/ai/recommendations');
  return response.data;
};

export const fetchSites = async () => {
  const response = await api.get('/sites');
  return response.data;
};

export const fetchOperators = async () => {
  const response = await api.get('/dashboard-operators');
  return response.data;
};

export const fetchTrends = async () => {
  const response = await api.get('/analytics/trends');
  return response.data;
};

export const fetchReports = async () => {
  const response = await api.get('/analytics/reports');
  return response.data;
};

export const fetchBrief = async () => {
  const response = await api.get('/analytics/brief');
  return response.data;
};

export const fetchMapMarkers = async () => {
  const response = await api.get('/live/map-markers');
  return response.data;
};

export const fetchActivity = async () => {
  const response = await api.get('/live/activity');
  return response.data;
};

export const askCopilot = async (query: string) => {
  const response = await api.post('/ai/copilot', { query });
  return response.data.reply;
};

// ---- ML-backed endpoints ----

export const fetchAnomalies = async (limit = 25, minSeverity?: string) => {
  const params: Record<string, any> = { limit };
  if (minSeverity) params.min_severity = minSeverity;
  const response = await api.get('/ai/anomalies', { params });
  return response.data;
};

export const fetchAnomalySummary = async () => {
  const response = await api.get('/ai/anomalies/summary');
  return response.data;
};

export const fetchModelMetrics = async () => {
  const response = await api.get('/ai/model-metrics');
  return response.data;
};

export const fetchForecastCountries = async () => {
  const response = await api.get('/analytics/forecast/countries');
  return response.data.countries as string[];
};

export const fetchForecastByCountry = async (country: string) => {
  const response = await api.get(`/analytics/forecast/country/${country}`);
  return response.data;
};

export const fetchForecastComparison = async (machineType?: string) => {
  const params = machineType ? { machine_type: machineType } : {};
  const response = await api.get('/analytics/forecast/comparison', { params });
  return response.data;
};

export const fetchMaintenanceForecast = async (assetId: string) => {
  const response = await api.get(`/equipment/${assetId}/maintenance-forecast`);
  return response.data;
};
