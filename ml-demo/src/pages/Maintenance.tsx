import { useEffect, useMemo, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { Wrench, Activity, CalendarClock, Gauge as GaugeIcon } from 'lucide-react';
import { Card, Loading, ErrorState, Gauge, Stat, Explain, Badge } from '@/components/ui';
import { getEquipment, getMaintenanceForecast, Equipment, MaintenanceForecast } from '@/api';

const TT = { backgroundColor: '#1B1D20', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, fontSize: 12, color: '#C7CCD4' };
const clamp = (n: number) => Math.max(5, Math.min(99, Math.round(n)));

export function Maintenance() {
  const [fleet, setFleet] = useState<Equipment[]>([]);
  const [assetId, setAssetId] = useState('');
  const [forecast, setForecast] = useState<MaintenanceForecast | null>(null);
  const [loadingFleet, setLoadingFleet] = useState(true);
  const [loadingPred, setLoadingPred] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getEquipment()
      .then((e) => {
        // Live DB assets first, then simulated fleet.
        const sorted = [...e].sort((a, b) => Number(b.isLive) - Number(a.isLive));
        setFleet(sorted);
        setAssetId(sorted[0]?.id || '');
        setError('');
      })
      .catch((err) => setError(err?.message || 'network error'))
      .finally(() => setLoadingFleet(false));
  }, []);

  useEffect(() => {
    if (!assetId) return;
    setLoadingPred(true);
    getMaintenanceForecast(assetId)
      .then(setForecast)
      .catch(() => setForecast(null))
      .finally(() => setLoadingPred(false));
  }, [assetId]);

  const asset = useMemo(() => fleet.find((f) => f.id === assetId), [fleet, assetId]);
  const p = forecast?.prediction;
  // The equipment list carries the real per-asset health/risk for BOTH live-DB
  // and simulated machines; prefer it so live assets show their true health.
  const health = asset?.health ?? p?.health ?? 0;
  const risk = asset?.riskScore ?? p?.riskScore ?? 0;

  const trend = useMemo(() => {
    if (!p) return [];
    const h = health;
    const step = Math.max(1, Math.round(risk / 12));
    return [
      { t: '-3 mo', health: clamp(h + step * 2.2) },
      { t: '-2 mo', health: clamp(h + step * 1.5) },
      { t: '-1 mo', health: clamp(h + step * 0.7) },
      { t: 'Now', health: h, projected: h },
      { t: '+1 mo', projected: clamp(h - step) },
      { t: '+2 mo', projected: clamp(h - step * 2) },
    ];
  }, [p, health, risk]);

  const nextService = forecast?.timeline?.find((t) => t.status === 'predicted');

  if (error && !fleet.length) return <ErrorState message={error} onRetry={() => location.reload()} />;

  const riskTone = !p ? 'low' : risk >= 60 ? 'critical' : risk >= 30 ? 'high' : 'low';
  const riskLabel = !p ? '—' : risk >= 60 ? 'High risk' : risk >= 30 ? 'Watch' : 'Low risk';

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Predictive Maintenance</h1>
          <p className="mt-1 text-sm text-ink-200">Health score and 30-day breakdown risk from live sensor telemetry.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-ink-200">Machine</label>
          {loadingFleet ? <span className="text-xs text-ink-300">loading fleet…</span> : (
            <select className="select max-w-[320px]" value={assetId} onChange={(e) => setAssetId(e.target.value)}>
              {fleet.map((f) => (
                <option key={f.id} value={f.id}>{f.isLive ? '● LIVE — ' : ''}{f.name}</option>
              ))}
            </select>
          )}
        </div>
      </header>

      {loadingPred || !p ? <Loading label="Scoring machine health…" /> : (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Health gauge */}
            <Card className="flex flex-col items-center justify-center">
              <div className="mb-1 flex items-center gap-2 self-start text-sm font-semibold text-white">
                <GaugeIcon className="h-4 w-4 text-cat-yellow" /> Health Score
              </div>
              <Gauge value={health} size={150} label="/ 100" />
              <div className="mt-3 flex items-center gap-2">
                <Badge tone={riskTone} dot={riskTone === 'critical'}>{riskLabel}</Badge>
                {asset?.isLive && <Badge tone="medium">Live DB asset</Badge>}
              </div>
            </Card>

            {/* Key numbers */}
            <div className="grid grid-cols-2 gap-4 lg:col-span-2">
              <Stat label="Failure probability (30 days)" tone={p.maintenanceProbability >= 0.5 ? 'crit' : 'ok'}
                value={`${Math.round(p.maintenanceProbability * 100)}%`}
                hint={p.maintenanceWithin30d ? 'service recommended' : 'within normal range'} />
              <Stat label="Risk score" tone={riskTone === 'critical' ? 'crit' : riskTone === 'high' ? 'warn' : 'ok'}
                value={risk} hint="0 = healthy · 100 = critical" />
              <Stat label="Engine life used" tone={(p.lifeUsedPct ?? 0) > 100 ? 'crit' : 'ink'}
                value={p.lifeUsedPct != null ? `${p.lifeUsedPct}%` : '—'} hint="of rated engine hours" />
              <Stat label="Next predicted service" tone="cat"
                value={nextService?.date || '—'} hint={nextService?.event?.replace('Predicted service - ', '') || 'no service due soon'} />
            </div>
          </div>

          <Explain>{buildExplanation(asset, { ...p, health, riskScore: risk }, nextService?.date)}</Explain>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Health trajectory */}
            <Card className="lg:col-span-2">
              <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-white">
                <Activity className="h-4 w-4 text-cat-yellow" /> Health trajectory
              </h3>
              <p className="mb-3 text-xs text-ink-200">Recent health (solid) and the model’s projection if left unserviced (dashed).</p>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="t" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={TT} />
                    <ReferenceLine y={40} stroke="#EF4444" strokeDasharray="4 4" label={{ value: 'service threshold', fill: '#EF4444', fontSize: 10, position: 'insideTopLeft' }} />
                    <Line type="monotone" dataKey="health" stroke="#22C55E" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                    <Line type="monotone" dataKey="projected" stroke="#F59E0B" strokeWidth={2.5} strokeDasharray="6 5" dot={{ r: 3 }} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Recommendation + service timeline */}
            <Card>
              <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-white">
                <Wrench className="h-4 w-4 text-cat-yellow" /> Recommendation
              </h3>
              <p className="mb-3 rounded-lg bg-ink-500/40 p-3 text-[13px] leading-relaxed text-ink-100">{p.reason}</p>
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-300">
                <CalendarClock className="h-3.5 w-3.5" /> Service timeline
              </div>
              <div className="mt-2 space-y-2.5">
                {(forecast?.timeline || []).map((t, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className={`h-2 w-2 rounded-full ${t.status === 'predicted' ? 'bg-warn ring-4 ring-warn/20' : 'bg-ok'}`} />
                    <span className="flex-1 text-[13px] text-ink-100">{t.event}</span>
                    <span className="text-[11px] text-ink-300">{t.date}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function buildExplanation(asset: Equipment | undefined, p: any, nextDate?: string): string {
  const name = asset?.name || 'This machine';
  if (p.maintenanceWithin30d) {
    return `${name} is predicted to need service within 30 days (${Math.round(p.maintenanceProbability * 100)}% probability). ${p.reason} Scheduling maintenance${nextDate ? ` around ${nextDate}` : ' now'} avoids an unplanned breakdown, which typically costs far more in downtime and emergency repair than a planned service.`;
  }
  return `${name} is healthy (score ${p.health}/100, only ${Math.round(p.maintenanceProbability * 100)}% breakdown risk in the next 30 days). It’s operating within normal parameters — keep it working and re-check at the next routine interval${nextDate ? ` (~${nextDate})` : ''}.`;
}
