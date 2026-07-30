import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldAlert, AlertTriangle, Fuel, MapPin, UserX, Activity,
  Gauge, Radio, Loader2, DollarSign,
} from 'lucide-react';
import { fetchAnomalies, fetchAnomalySummary } from '@/services/api';

const SEVERITY_STYLE: Record<string, { chip: string; dot: string; label: string }> = {
  critical: { chip: 'bg-crit/15 text-crit border-crit/30', dot: 'bg-crit', label: 'Critical' },
  high:     { chip: 'bg-warn/15 text-warn border-warn/30', dot: 'bg-warn', label: 'High' },
  medium:   { chip: 'bg-info/15 text-info border-info/30', dot: 'bg-info', label: 'Medium' },
  low:      { chip: 'bg-ink-500/40 text-ink-200 border-white/10', dot: 'bg-ink-300', label: 'Low' },
};

const TYPE_ICON: Record<string, any> = {
  unauthorized_use: UserX,
  unaccounted_asset: MapPin,
  geofence_breach: MapPin,
  fuel_anomaly: Fuel,
  impossible_hours: Gauge,
  gps_jump: Radio,
  sensor_failure: Radio,
  excess_idle: Activity,
  missing_operator_at_checkout: UserX,
};

export function AnomalyMonitor({ limit = 12 }: { limit?: number }) {
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchAnomalies(limit), fetchAnomalySummary()])
      .then(([a, s]) => {
        setAnomalies(Array.isArray(a) ? a : (a.anomalies || []));
        setSummary(s);
      })
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, [limit]);

  const filtered = filter === 'all' ? anomalies : anomalies.filter((a) => a.severity === filter);

  return (
    <div className="card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-crit/10 text-crit">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">AI Anomaly Detection</h3>
            <p className="text-xs text-ink-200">
              Hybrid model — CAT telemetry signals + behavioral outlier scoring
            </p>
          </div>
        </div>
        {summary && (
          <div className="flex items-center gap-2 rounded-lg border border-crit/20 bg-crit/[0.06] px-3 py-1.5">
            <DollarSign className="h-4 w-4 text-crit" />
            <span className="text-xs text-ink-100">
              <span className="font-bold text-crit">${summary.estimatedDailyExposure?.toLocaleString()}</span> daily exposure
            </span>
          </div>
        )}
      </div>

      {/* Severity summary band */}
      {summary && (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(['critical', 'high', 'medium'] as const).map((sev) => (
            <button
              key={sev}
              onClick={() => setFilter(filter === sev ? 'all' : sev)}
              className={`rounded-lg border p-3 text-left transition-all ${SEVERITY_STYLE[sev].chip} ${
                filter === sev ? 'ring-2 ring-white/20' : ''
              }`}
            >
              <div className="text-2xl font-bold">{summary.bySeverity?.[sev] ?? 0}</div>
              <div className="text-[10px] font-medium uppercase tracking-wider opacity-80">{SEVERITY_STYLE[sev].label}</div>
            </button>
          ))}
          <div className="rounded-lg border border-white/10 bg-ink-500/40 p-3">
            <div className="text-2xl font-bold text-white">{summary.totalAnomalies ?? 0}</div>
            <div className="text-[10px] font-medium uppercase tracking-wider text-ink-200">Total Flagged</div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex h-[240px] items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-cat-yellow" />
        </div>
      ) : (
        <div className="scrollbar-thin max-h-[420px] space-y-2 overflow-y-auto pr-1">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <ShieldAlert className="mb-2 h-8 w-8 text-ink-300" />
              <p className="text-sm text-ink-200">No anomalies at this severity.</p>
            </div>
          ) : (
            filtered.map((a, i) => {
              const Icon = TYPE_ICON[a.anomalyType] || AlertTriangle;
              const sev = SEVERITY_STYLE[a.severity] || SEVERITY_STYLE.medium;
              return (
                <motion.div
                  key={a.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="flex items-start gap-3 rounded-lg border border-white/[0.05] bg-ink-500/30 p-3"
                >
                  <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${sev.chip}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-white">{a.anomalyLabel}</span>
                      <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${sev.chip}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${sev.dot}`} />
                        {sev.label}
                      </span>
                      <span className="text-[10px] text-ink-300">· {a.confidence}% confidence</span>
                    </div>
                    <div className="mt-0.5 text-xs text-ink-200">
                      {a.equipment} <span className="text-ink-300">({a.equipmentType})</span> · {a.detectedOn}
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-ink-100">{a.reason}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-sm font-bold text-crit">${a.estimatedDailyCost?.toLocaleString()}</div>
                    <div className="text-[9px] uppercase tracking-wider text-ink-300">per day</div>
                  </div>
                </motion.div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
