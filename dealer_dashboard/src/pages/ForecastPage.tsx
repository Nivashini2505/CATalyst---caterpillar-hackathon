import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { TrendingUp, DollarSign, Activity, CalendarClock, Loader2 } from 'lucide-react';
import { fetchTrends } from '@/services/api';
import { PageContainer, PageHeader } from '@/components/ui/Page';
import { CountryForecastPanel } from '@/components/mission/CountryForecastPanel';

const tooltipStyle = {
  backgroundColor: '#1B1D20', border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '0.75rem', fontSize: '0.75rem', color: '#C7CCD4',
};

export function ForecastPage() {
  const [trends, setTrends] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchTrends();
        setTrends(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <PageContainer title="Forecasting">
      <PageHeader title="Forecasting" subtitle="Predictive analytics for demand, revenue, utilization, and rentals." />
      <div className="mb-6">
        <CountryForecastPanel />
      </div>

      {loading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-8 w-8 animate-spin text-cat-yellow" /></div>
      ) : (
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard icon={<TrendingUp className="h-5 w-5" />} title="Demand Forecast" subtitle="7-day equipment demand by category" delay={0}>
          <AreaChart data={trends?.demandForecast || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              {[
                { k: 'Excavators', c: '#FFCD11' }, { k: 'Dozers', c: '#22C55E' },
                { k: 'Loaders', c: '#3B82F6' }, { k: 'Graders', c: '#F59E0B' },
              ].map((s) => (
                <linearGradient key={s.k} id={`fc-${s.k}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={s.c} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={s.c} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="day" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area type="monotone" dataKey="Excavators" stroke="#FFCD11" strokeWidth={2} fill="url(#fc-Excavators)" />
            <Area type="monotone" dataKey="Dozers" stroke="#22C55E" strokeWidth={2} fill="url(#fc-Dozers)" />
            <Area type="monotone" dataKey="Loaders" stroke="#3B82F6" strokeWidth={2} fill="url(#fc-Loaders)" />
            <Area type="monotone" dataKey="Graders" stroke="#F59E0B" strokeWidth={2} fill="url(#fc-Graders)" />
          </AreaChart>
        </ChartCard>

        <ChartCard icon={<DollarSign className="h-5 w-5" />} title="Revenue Trend" subtitle="Monthly revenue vs target ($K)" delay={0.06}>
          <BarChart data={trends?.revenueTrend || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="target" fill="#3A3F47" radius={[4, 4, 0, 0]} />
            <Bar dataKey="revenue" fill="#FFCD11" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard icon={<Activity className="h-5 w-5" />} title="Utilization Trend" subtitle="Weekly utilization vs idle %" delay={0.12}>
          <LineChart data={trends?.utilizationTrend || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="week" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="utilization" stroke="#22C55E" strokeWidth={2.5} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="idle" stroke="#F59E0B" strokeWidth={2.5} dot={{ r: 3 }} />
          </LineChart>
        </ChartCard>

        <ChartCard icon={<CalendarClock className="h-5 w-5" />} title="Rental Trends" subtitle="New, expiring, and renewed rentals per month" delay={0.18}>
          <BarChart data={trends?.rentalTrends || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="new" fill="#FFCD11" radius={[4, 4, 0, 0]} />
            <Bar dataKey="renewed" fill="#22C55E" radius={[4, 4, 0, 0]} />
            <Bar dataKey="expiring" fill="#EF4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
      </div>
      )}
    </PageContainer>
  );
}

function ChartCard({
  icon, title, subtitle, children, delay,
}: {
  icon: React.ReactNode; title: string; subtitle: string; children: React.ReactNode; delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="card p-5"
    >
      <div className="mb-4 flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat-yellow/10 text-cat-yellow">
          {icon}
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          <p className="text-xs text-ink-200">{subtitle}</p>
        </div>
      </div>
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          {children as any}
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
