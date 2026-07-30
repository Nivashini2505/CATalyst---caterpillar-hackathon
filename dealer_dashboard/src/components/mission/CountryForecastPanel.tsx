import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { Globe2, TrendingUp, TrendingDown, Minus, Loader2 } from 'lucide-react';
import { fetchForecastCountries, fetchForecastByCountry, fetchForecastComparison } from '@/services/api';

const tooltipStyle = {
  backgroundColor: '#1B1D20', border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '0.75rem', fontSize: '0.75rem', color: '#C7CCD4',
};
const COUNTRY_FLAG: Record<string, string> = {
  India: '🇮🇳', USA: '🇺🇸', Germany: '🇩🇪', Australia: '🇦🇺',
};

export function CountryForecastPanel() {
  const [countries, setCountries] = useState<string[]>([]);
  const [active, setActive] = useState<string>('India');
  const [series, setSeries] = useState<any[]>([]);
  const [comparison, setComparison] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchForecastCountries().then((cs) => {
      setCountries(cs);
      if (cs.length && !cs.includes(active)) setActive(cs[0]);
    }).catch(() => setCountries(['India', 'USA', 'Germany', 'Australia']));
  }, []);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    Promise.all([
      fetchForecastByCountry(active),
      fetchForecastComparison('Excavator'),
    ]).then(([byCountry, comp]) => {
      setSeries(byCountry.series || []);
      setComparison(comp.data || []);
    }).finally(() => setLoading(false));
  }, [active]);

  const top = series.slice(0, 8);

  return (
    <div className="card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat-yellow/10 text-cat-yellow">
            <Globe2 className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Demand Forecast by Country</h3>
            <p className="text-xs text-ink-200">ML-predicted next-week bookings per equipment type</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {countries.map((c) => (
            <button
              key={c}
              onClick={() => setActive(c)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                active === c ? 'bg-cat-yellow text-ink-900' : 'bg-ink-500/40 text-ink-100 hover:bg-ink-500/60'
              }`}
            >
              <span className="mr-1">{COUNTRY_FLAG[c] || '🏳️'}</span>{c}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex h-[300px] items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-cat-yellow" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* Per-type forecast list for selected country */}
          <div>
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ink-200">
              {active} · next-week outlook by type
            </div>
            <div className="space-y-1.5">
              {top.map((s, i) => (
                <motion.div
                  key={s.machineType}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-center gap-3 rounded-lg bg-ink-500/30 px-3 py-2"
                >
                  <div className="flex-1">
                    <div className="text-sm font-medium text-ink-50">{s.machineType}</div>
                    <div className="text-[10px] text-ink-200">4-wk avg {s.recentAvg}</div>
                  </div>
                  <div className="w-24">
                    <div className="h-1.5 overflow-hidden rounded-full bg-ink-400">
                      <div
                        className={`h-full rounded-full ${
                          s.demandLevel === 'High' ? 'bg-ok' : s.demandLevel === 'Medium' ? 'bg-cat-yellow' : 'bg-ink-300'
                        }`}
                        style={{ width: `${Math.min(100, (s.forecastNextWeek / 25) * 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="w-14 text-right text-sm font-bold text-white">{s.forecastNextWeek}</div>
                  <div className="w-5">
                    {s.trend === 'up' ? <TrendingUp className="h-4 w-4 text-ok" />
                      : s.trend === 'down' ? <TrendingDown className="h-4 w-4 text-crit" />
                      : <Minus className="h-4 w-4 text-ink-300" />}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Cross-country comparison for a reference type */}
          <div>
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ink-200">
              Excavator demand · all countries
            </div>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={comparison} layout="vertical" margin={{ top: 6, right: 16, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="country" type="category" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} width={72} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="forecast" radius={[0, 4, 4, 0]}>
                    {comparison.map((entry, i) => (
                      <Cell key={i} fill={entry.country === active ? '#FFCD11' : '#3A3F47'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
