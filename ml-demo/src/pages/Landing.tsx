import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { TrendingUp, ShieldAlert, Wrench, ArrowRight, Sparkles } from 'lucide-react';
import { getModelMetrics } from '@/api';

const MODULES = [
  {
    to: '/demand', icon: TrendingUp, tone: 'text-cat-yellow bg-cat-yellow/10 border-cat-yellow/20',
    title: 'Demand Forecasting',
    desc: 'Predict next-week equipment demand per country and machine type, so dealers pre-position the right machines.',
    tag: 'Gradient Boosting',
  },
  {
    to: '/anomaly', icon: ShieldAlert, tone: 'text-crit bg-crit/10 border-crit/20',
    title: 'Anomaly Detection',
    desc: 'Flag misuse, unauthorized use, fuel loss and idle waste in real time — with the dollar impact of each issue.',
    tag: 'IsolationForest + RandomForest',
  },
  {
    to: '/maintenance', icon: Wrench, tone: 'text-info bg-info/10 border-info/20',
    title: 'Predictive Maintenance',
    desc: 'Score every machine’s health 0–100 and predict breakdowns 30 days ahead from live sensor telemetry.',
    tag: 'RandomForest + Gradient Boosting',
  },
];

export function Landing() {
  const [metrics, setMetrics] = useState<any>(null);
  useEffect(() => { getModelMetrics().then(setMetrics).catch(() => setMetrics(null)); }, []);
  const loaded = metrics?.modelsLoaded;

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        className="relative overflow-hidden rounded-3xl border border-white/[0.06] bg-ink-600/60 p-8 md:p-12"
      >
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-cat-yellow/10 blur-3xl" />
        <div className="relative">
          <div className="mb-3 flex items-center gap-2 text-cat-yellow">
            <Sparkles className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-widest">AI Fleet Intelligence</span>
          </div>
          <h1 className="max-w-2xl text-4xl font-extrabold leading-tight tracking-tight text-white md:text-5xl">
            Turn rental telemetry into <span className="text-cat-yellow">decisions</span>.
          </h1>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-100">
            Three production ML models running live on the CAT-alyst fleet — forecasting demand,
            catching misuse, and predicting breakdowns before they happen.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            {loaded ? (
              <>
                <MetricChip ok={loaded.demand} label={`Demand model ${loaded.demand ? 'live' : 'offline'}`} />
                <MetricChip ok={loaded.anomaly} label={`Anomaly model ${loaded.anomaly ? 'live' : 'offline'}`} />
                <MetricChip ok={loaded.maintenance} label={`Maintenance model ${loaded.maintenance ? 'live' : 'offline'}`} />
              </>
            ) : (
              <span className="text-xs text-ink-300">Connecting to ML backend…</span>
            )}
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {MODULES.map((m, i) => (
          <motion.div key={m.to}
            initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.08, duration: 0.45 }}>
            <Link to={m.to} className="card card-hover group block h-full p-6">
              <div className={`flex h-12 w-12 items-center justify-center rounded-xl border ${m.tone}`}>
                <m.icon className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-white">{m.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-200">{m.desc}</p>
              <div className="mt-4 flex items-center justify-between">
                <span className="chip border border-white/10 bg-ink-500/40 text-ink-200">{m.tag}</span>
                <span className="inline-flex items-center gap-1 text-sm font-semibold text-cat-yellow opacity-0 transition-opacity group-hover:opacity-100">
                  Open <ArrowRight className="h-4 w-4" />
                </span>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function MetricChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`chip border ${ok ? 'border-ok/30 bg-ok/10 text-ok' : 'border-crit/30 bg-crit/10 text-crit'}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? 'bg-ok' : 'bg-crit'}`} /> {label}
    </span>
  );
}
