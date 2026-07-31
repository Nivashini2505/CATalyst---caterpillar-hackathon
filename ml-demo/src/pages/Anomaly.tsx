import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldAlert, DollarSign, Cpu, MapPin } from 'lucide-react';
import { Card, Loading, ErrorState, Badge, Stat } from '@/components/ui';
import { getAnomalies, getAnomalySummary, AnomalyEvent, AnomalySummary } from '@/api';

const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low'] as const;
type Sev = typeof SEVERITIES[number];

export function Anomaly() {
  const [summary, setSummary] = useState<AnomalySummary | null>(null);
  const [events, setEvents] = useState<AnomalyEvent[]>([]);
  const [filter, setFilter] = useState<Sev>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    Promise.all([getAnomalySummary(), getAnomalies(200)])
      .then(([s, e]) => { setSummary(s); setEvents(e); setError(''); })
      .catch((err) => setError(err?.message || 'network error'))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const filtered = useMemo(
    () => (filter === 'all' ? events : events.filter((e) => e.severity === filter)),
    [events, filter],
  );

  if (error && !events.length) return <ErrorState message={error} onRetry={load} />;

  const sev = summary?.bySeverity;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Anomaly Detection</h1>
        <p className="mt-1 text-sm text-ink-200">
          Live misuse, theft and idle-waste alerts — each with the business impact and a plain-English reason.
        </p>
      </header>

      {loading && !summary ? <Loading label="Scanning fleet telemetry…" /> : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <Stat label="Critical" tone="crit" value={sev?.critical ?? 0} hint="act now" />
            <Stat label="High" tone="warn" value={sev?.high ?? 0} hint="investigate" />
            <Stat label="Medium" tone="info" value={sev?.medium ?? 0} hint="monitor" />
            <Stat label="Low" value={sev?.low ?? 0} hint="informational" />
            <Stat label="Revenue at risk / day" tone="cat"
              value={`$${(summary?.estimatedDailyExposure ?? 0).toLocaleString()}`}
              hint={`${summary?.totalAnomalies ?? 0} active anomalies`} />
          </div>

          {/* Filter */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-ink-200">Filter by severity:</span>
            {SEVERITIES.map((s) => (
              <button key={s} onClick={() => setFilter(s)}
                className={`chip border capitalize ${
                  filter === s ? 'border-cat-yellow/40 bg-cat-yellow/10 text-cat-yellow' : 'border-white/10 bg-ink-500/40 text-ink-200 hover:text-ink-50'
                }`}>
                {s} {s !== 'all' && sev ? `(${(sev as any)[s] ?? 0})` : ''}
              </button>
            ))}
            <span className="ml-auto text-xs text-ink-300">{filtered.length} shown</span>
          </div>

          {/* Anomaly list */}
          {filtered.length === 0 ? (
            <Card><div className="py-10 text-center text-sm text-ink-200">No anomalies at this severity. Fleet is clean here. ✅</div></Card>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {filtered.map((e, i) => (
                <motion.div key={e.id}
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.03, 0.4) }}>
                  <div className="card h-full p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-crit/10 text-crit">
                          <ShieldAlert className="h-5 w-5" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{e.anomalyLabel}</div>
                          <div className="text-[11px] text-ink-300">{e.equipment} · <span className="font-mono">{e.assetId}</span></div>
                        </div>
                      </div>
                      <Badge tone={e.severity} dot={e.severity === 'critical'}>{e.severity}</Badge>
                    </div>

                    <p className="mt-3 rounded-lg bg-ink-500/40 p-3 text-[13px] leading-relaxed text-ink-100">{e.reason}</p>

                    <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                      <div className="rounded-lg border border-white/[0.06] bg-ink-500/30 p-2">
                        <div className="flex items-center justify-center gap-1 text-[10px] uppercase tracking-wider text-ink-300"><DollarSign className="h-3 w-3" />Impact/day</div>
                        <div className="mt-0.5 text-sm font-bold text-cat-yellow">${e.estimatedDailyCost.toLocaleString()}</div>
                      </div>
                      <div className="rounded-lg border border-white/[0.06] bg-ink-500/30 p-2">
                        <div className="flex items-center justify-center gap-1 text-[10px] uppercase tracking-wider text-ink-300"><Cpu className="h-3 w-3" />Confidence</div>
                        <div className="mt-0.5 text-sm font-bold text-white">{e.confidence}%</div>
                      </div>
                      <div className="rounded-lg border border-white/[0.06] bg-ink-500/30 p-2">
                        <div className="flex items-center justify-center gap-1 text-[10px] uppercase tracking-wider text-ink-300"><MapPin className="h-3 w-3" />Site</div>
                        <div className="mt-0.5 truncate text-sm font-medium text-ink-100">{e.site}</div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
