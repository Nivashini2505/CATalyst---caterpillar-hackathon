import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft, MapPin, User, Wrench, Clock, Gauge, Sparkles,
  TrendingUp, AlertTriangle, CalendarClock, Loader2
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { fetchEquipment, fetchRecommendations, fetchMaintenanceForecast } from '@/services/api';
import { Badge, statusTone } from '@/components/ui/Badge';
import { RingGauge } from '@/components/ui/RingGauge';
import { Button } from '@/components/ui/Button';
import { PageContainer, EmptyState } from '@/components/ui/Page';
import { RecommendationCard } from '@/components/mission/RecommendationCard';

const statusLabel: Record<string, string> = {
  working: 'Working', idle: 'Idle', critical: 'Critical', maintenance: 'Maintenance', transit: 'Transit',
};

const tooltipStyle = {
  backgroundColor: '#1B1D20', border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '0.75rem', fontSize: '0.75rem', color: '#C7CCD4',
};

// Synthetic hourly health trend
const healthTrend = Array.from({ length: 12 }, (_, i) => ({
  hour: `${i * 2}:00`,
  health: Math.max(50, 96 - i * 1.5 - Math.random() * 4),
}));

const fallbackTimeline = [
  { date: 'Jul 28', event: 'Hydraulic inspection', status: 'done' },
  { date: 'Jul 15', event: 'Oil change', status: 'done' },
  { date: 'Jul 02', event: 'Track adjustment', status: 'done' },
  { date: 'Aug 12', event: 'Next service interval', status: 'upcoming' },
];

export function EquipmentDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [eq, setEq] = useState<any>(null);
  const [rec, setRec] = useState<any>(null);
  const [maintenance, setMaintenance] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [eqData, recData] = await Promise.all([fetchEquipment(), fetchRecommendations()]);
        setEq(eqData.find((e: any) => e.id === id) || null);
        setRec(recData.find((r: any) => r.equipmentId === id) || null);
        if (id) {
          fetchMaintenanceForecast(id).then(setMaintenance).catch(() => setMaintenance(null));
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const maintenanceTimeline = maintenance?.timeline || fallbackTimeline;

  if (loading) {
    return (
      <PageContainer title="Equipment">
        <div className="flex justify-center p-12"><Loader2 className="h-8 w-8 animate-spin text-cat-yellow" /></div>
      </PageContainer>
    );
  }

  if (!eq) {
    return (
      <PageContainer title="Equipment">
        <div className="card">
          <EmptyState icon={<AlertTriangle className="h-6 w-6" />} title="Equipment not found" description="This asset may have been removed." />
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer title={eq.name}>
      <button
        onClick={() => navigate('/fleet')}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-200 transition-colors hover:text-ink-50"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Fleet
      </button>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: image + vitals */}
        <div className="lg:col-span-1 space-y-4">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="card overflow-hidden"
          >
            <div className="relative h-56">
              <img src={eq.image} alt={eq.name} className="h-full w-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-ink-600 via-transparent to-transparent" />
              <div className="absolute left-4 top-4">
                <Badge tone={statusTone(eq.status)} dot={eq.status === 'critical'}>
                  {statusLabel[eq.status]}
                </Badge>
              </div>
            </div>
            <div className="p-5">
              <h2 className="text-xl font-bold text-white">{eq.name}</h2>
              <p className="text-sm text-ink-200">{eq.model} · {eq.category}</p>
              <div className="mt-4 space-y-2.5 text-sm">
                <Row icon={<MapPin className="h-4 w-4" />} label="Current Site" value={eq.site} />
                <Row icon={<User className="h-4 w-4" />} label="Operator" value={eq.operator} />
                <Row icon={<Gauge className="h-4 w-4" />} label="Engine Hours" value={`${eq.engineHours.toLocaleString()} h`} />
                <Row icon={<Clock className="h-4 w-4" />} label="Idle Hours" value={`${eq.idleHours} h`} />
                <Row icon={<CalendarClock className="h-4 w-4" />} label="Rental Remaining" value={`${eq.rentalRemainingDays} days`} />
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card grid grid-cols-2 gap-4 p-5">
            <div className="flex flex-col items-center">
              <RingGauge value={eq.health} size={84} stroke={8} tone={eq.health > 85 ? 'ok' : eq.health > 70 ? 'warn' : 'crit'} label="health" />
              <div className="mt-2 text-xs text-ink-200">Health Score</div>
            </div>
            <div className="flex flex-col items-center">
              <RingGauge value={eq.riskScore} size={84} stroke={8} tone={eq.riskScore < 30 ? 'ok' : eq.riskScore < 60 ? 'warn' : 'crit'} label="risk" />
              <div className="mt-2 text-xs text-ink-200">Risk Score</div>
            </div>
          </motion.div>
        </div>

        {/* Right: charts + timeline + AI */}
        <div className="lg:col-span-2 space-y-4">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="card p-5">
            <div className="mb-3 flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat-yellow/10 text-cat-yellow">
                <TrendingUp className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Health Trend (24h)</h3>
                <p className="text-xs text-ink-200">Hourly health score readings</p>
              </div>
            </div>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={healthTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="grad-health" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22C55E" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#22C55E" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="hour" tick={{ fill: '#8A93A1', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[40, 100]} tick={{ fill: '#8A93A1', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="health" stroke="#22C55E" strokeWidth={2} fill="url(#grad-health)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="card p-5">
              <div className="mb-3 flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-info/10 text-info">
                  <CalendarClock className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-semibold text-white">Rental Timeline</h3>
              </div>
              <div className="space-y-3">
                {[
                  { label: 'Start', date: 'Jul 10', done: true },
                  { label: 'Current', date: 'Today', done: true, active: true },
                  { label: 'Expiry', date: `+${eq.rentalRemainingDays}d`, done: false },
                ].map((s) => (
                  <div key={s.label} className="flex items-center gap-3">
                    <div className={`h-2.5 w-2.5 rounded-full ${s.active ? 'bg-cat-yellow ring-4 ring-cat-yellow/20' : s.done ? 'bg-ok' : 'bg-ink-400'}`} />
                    <div className="flex-1">
                      <div className="text-sm text-ink-50">{s.label}</div>
                    </div>
                    <div className="text-xs text-ink-200">{s.date}</div>
                  </div>
                ))}
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-400">
                  <div className="h-full rounded-full bg-cat-yellow" style={{ width: '68%' }} />
                </div>
              </div>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="card p-5">
              <div className="mb-3 flex items-center justify-between gap-2.5">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-info/10 text-info">
                    <Wrench className="h-5 w-5" />
                  </div>
                  <h3 className="text-sm font-semibold text-white">Predictive Maintenance</h3>
                </div>
                {maintenance?.prediction && (
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    maintenance.prediction.maintenanceWithin30d
                      ? 'bg-crit/15 text-crit' : 'bg-ok/15 text-ok'
                  }`}>
                    {maintenance.prediction.maintenanceWithin30d ? 'Service due <30d' : 'Healthy'}
                  </span>
                )}
              </div>
              {maintenance?.prediction && (
                <div className="mb-3 rounded-lg border border-info/15 bg-info/[0.04] p-2.5">
                  <p className="text-xs leading-relaxed text-ink-100">{maintenance.prediction.reason}</p>
                  <div className="mt-1.5 flex items-center gap-3 text-[10px] text-ink-200">
                    <span>Life used <span className="font-semibold text-ink-50">{maintenance.prediction.lifeUsedPct}%</span></span>
                    <span>Risk <span className="font-semibold text-ink-50">{maintenance.prediction.riskScore}%</span></span>
                    <span>Vibration <span className="font-semibold text-ink-50">{maintenance.prediction.vibration}g</span></span>
                  </div>
                </div>
              )}
              <div className="space-y-3">
                {maintenanceTimeline.map((m: any) => (
                  <div key={m.date + m.event} className="flex items-center gap-3">
                    <div className={`h-2.5 w-2.5 rounded-full ${
                      m.status === 'done' ? 'bg-ok' : m.status === 'predicted' ? 'bg-cat-yellow ring-4 ring-cat-yellow/20' : 'bg-warn'
                    }`} />
                    <div className="flex-1 text-sm text-ink-50">{m.event}</div>
                    {m.status === 'predicted' && m.confidence != null && (
                      <div className="text-[10px] font-medium text-cat-yellow">{m.confidence}%</div>
                    )}
                    <div className="text-xs text-ink-200">{m.date}</div>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>

          {rec && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              <div className="mb-3 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-cat-yellow" />
                <h3 className="text-sm font-semibold text-white">AI Recommendation for this asset</h3>
              </div>
              <RecommendationCard rec={rec} />
            </motion.div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-ink-200">
        <span className="text-ink-200">{icon}</span>
        {label}
      </span>
      <span className="font-medium text-ink-50">{value}</span>
    </div>
  );
}
