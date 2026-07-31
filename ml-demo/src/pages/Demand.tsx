import { useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LineChart, Line, Legend,
} from 'recharts';
import { TrendingUp, TrendingDown, Minus, Globe2 } from 'lucide-react';
import { Card, Loading, ErrorState, Stat, Explain, Badge } from '@/components/ui';
import {
  getForecastCountries, getForecastByCountry, getForecastComparison, getTrends, getModelMetrics,
  CountrySeriesRow,
} from '@/api';

const TT = { backgroundColor: '#1B1D20', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, fontSize: 12, color: '#C7CCD4' };
const FLAG: Record<string, string> = { India: '🇮🇳', USA: '🇺🇸', Germany: '🇩🇪', Australia: '🇦🇺' };

export function Demand() {
  const [countries, setCountries] = useState<string[]>([]);
  const [country, setCountry] = useState('');
  const [series, setSeries] = useState<CountrySeriesRow[]>([]);
  const [machineType, setMachineType] = useState('');
  const [comparison, setComparison] = useState<{ country: string; forecast: number }[]>([]);
  const [weekly, setWeekly] = useState<any[]>([]);
  const [r2, setR2] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [cs, trends, metrics] = await Promise.all([getForecastCountries(), getTrends(), getModelMetrics()]);
        setCountries(cs);
        setCountry(cs[0] || 'India');
        setWeekly(trends.demandForecast || []);
        setR2(metrics?.demand?.R2 ?? null);
      } catch (e: any) { setError(e?.message || 'network error'); }
    })();
  }, []);

  useEffect(() => {
    if (!country) return;
    setLoading(true);
    getForecastByCountry(country)
      .then((d) => {
        setSeries(d.series);
        setMachineType(d.series[0]?.machineType || '');
        setError('');
      })
      .catch((e) => setError(e?.message || 'network error'))
      .finally(() => setLoading(false));
  }, [country]);

  useEffect(() => {
    if (!machineType) return;
    getForecastComparison(machineType).then((d) => setComparison(d.data)).catch(() => setComparison([]));
  }, [machineType]);

  const selected = useMemo(() => series.find((s) => s.machineType === machineType), [series, machineType]);

  if (error && !series.length) return <ErrorState message={error} onRetry={() => location.reload()} />;

  const trendIcon = selected?.trend === 'up' ? <TrendingUp className="h-4 w-4 text-ok" />
    : selected?.trend === 'down' ? <TrendingDown className="h-4 w-4 text-crit" />
    : <Minus className="h-4 w-4 text-ink-200" />;

  const explanation = selected ? buildExplanation(selected, country) : '';

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Demand Forecasting</h1>
          <p className="mt-1 text-sm text-ink-200">Predicted equipment rentals for next week, by country and machine type.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs text-ink-200">Country</label>
          <select className="select" value={country} onChange={(e) => setCountry(e.target.value)}>
            {countries.map((c) => <option key={c} value={c}>{FLAG[c] || ''} {c}</option>)}
          </select>
          <label className="ml-2 text-xs text-ink-200">Equipment</label>
          <select className="select" value={machineType} onChange={(e) => setMachineType(e.target.value)}>
            {series.map((s) => <option key={s.machineType} value={s.machineType}>{s.machineType}</option>)}
          </select>
        </div>
      </header>

      {loading ? <Loading /> : (
        <>
          {/* Prediction summary */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Predicted rentals (next week)" tone="cat" value={selected?.forecastNextWeek ?? '—'} hint={`${machineType} · ${country}`} />
            <Stat label="4-week average" value={selected?.recentAvg ?? '—'} hint="recent baseline" />
            <Stat label="Demand trend"
              tone={selected?.trend === 'up' ? 'ok' : selected?.trend === 'down' ? 'crit' : 'ink'}
              value={<span className="flex items-center gap-2">{trendIcon}{selected ? (selected.delta > 0 ? '+' : '') + selected.delta : '—'}</span>}
              hint="vs 4-week avg" />
            <Stat label="Demand level" value={<Badge tone={selected?.demandLevel === 'High' ? 'high' : selected?.demandLevel === 'Medium' ? 'medium' : 'low'}>{selected?.demandLevel || '—'}</Badge>}
              hint={r2 != null ? `model R² ${r2.toFixed(2)}` : 'ML forecast'} />
          </div>

          {selected && <Explain>{explanation}</Explain>}

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            {/* Full fleet demand for the country */}
            <Card>
              <h3 className="mb-1 text-sm font-semibold text-white">{country} — next-week demand by equipment</h3>
              <p className="mb-3 text-xs text-ink-200">Click an equipment type above to focus it.</p>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={series} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="machineType" tick={{ fill: '#8A93A1', fontSize: 10 }} angle={-25} textAnchor="end" height={70} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={TT} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                    <Bar dataKey="forecastNextWeek" radius={[4, 4, 0, 0]}>
                      {series.map((s) => (
                        <Cell key={s.machineType} fill={s.machineType === machineType ? '#FFCD11' : '#3A3F47'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Cross-country comparison for selected type */}
            <Card>
              <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-white">
                <Globe2 className="h-4 w-4 text-cat-yellow" /> {machineType} demand across countries
              </h3>
              <p className="mb-3 text-xs text-ink-200">Where this machine is needed most next week.</p>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparison} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="country" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={TT} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                    <Bar dataKey="forecast" radius={[4, 4, 0, 0]}>
                      {comparison.map((c) => <Cell key={c.country} fill={c.country === country ? '#FFCD11' : '#3A3F47'} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          {/* 7-day headline trend */}
          <Card>
            <h3 className="mb-1 text-sm font-semibold text-white">7-day demand outlook (all countries)</h3>
            <p className="mb-3 text-xs text-ink-200">Headline categories the fleet will need this week.</p>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={weekly} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="day" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TT} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="Excavators" stroke="#FFCD11" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Dozers" stroke="#22C55E" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Loaders" stroke="#3B82F6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Graders" stroke="#F59E0B" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function buildExplanation(s: CountrySeriesRow, country: string): string {
  const dir = s.trend === 'up' ? 'rising' : s.trend === 'down' ? 'softening' : 'steady';
  const action = s.demandLevel === 'High' || s.trend === 'up'
    ? `Pre-position extra ${s.machineType.toLowerCase()} units in ${country} now to capture the rentals and avoid stock-outs.`
    : s.demandLevel === 'Low' || s.trend === 'down'
      ? `Demand is soft — consider redeploying idle ${s.machineType.toLowerCase()} units to a higher-demand region instead of leaving them here.`
      : `Hold current allocation; demand is stable and well matched to supply.`;
  const deltaTxt = s.delta === 0 ? 'in line with' : `${Math.abs(s.delta)} ${s.delta > 0 ? 'above' : 'below'}`;
  return `The model forecasts about ${s.forecastNextWeek} ${s.machineType.toLowerCase()} rentals in ${country} next week — ${deltaTxt} the recent 4-week average of ${s.recentAvg}, a ${dir} ${s.demandLevel.toLowerCase()}-demand signal. ${action}`;
}
