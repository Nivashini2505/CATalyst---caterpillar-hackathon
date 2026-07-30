import { useState, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Brain, Check, X, TrendingUp, DollarSign, Sparkles, Filter, Loader2 } from 'lucide-react';
import { fetchRecommendations } from '@/services/api';

import { Badge, priorityTone } from '@/components/ui/Badge';
import { AnimatedCounter } from '@/components/ui/AnimatedCounter';
import { PageContainer, PageHeader } from '@/components/ui/Page';
import { RecommendationCard } from '@/components/mission/RecommendationCard';
import { AnomalyMonitor } from '@/components/mission/AnomalyMonitor';

const categories = ['All', 'Security', 'Maintenance', 'Utilization', 'Relocation', 'Rental'];
const priorities = ['All', 'high', 'medium', 'low'];

export function DecisionCenterPage() {
  const [cat, setCat] = useState('All');
  const [pri, setPri] = useState('All');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const data = await fetchRecommendations();
        setRecommendations(data);
      } catch (err) {
        console.error("Failed to fetch recommendations", err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const filtered = useMemo(
    () =>
      recommendations.filter(
        (r) => (cat === 'All' || r.category === cat) && (pri === 'All' || r.priority === pri)
      ),
    [cat, pri]
  );

  const totalSavings = recommendations.reduce((s, r) => s + r.savings, 0);
  const avgConfidence = Math.round(
    recommendations.reduce((s, r) => s + r.confidence, 0) / recommendations.length
  );
  const highPriority = recommendations.filter((r) => r.priority === 'high').length;

  return (
    <PageContainer title="Decision Center">
      <PageHeader
        title="Decision Center"
        subtitle="Your enterprise action center — every recommendation engineered to drive a decision."
      />

      {/* Summary band */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryCard
          icon={<Brain className="h-5 w-5" />}
          label="Active Recommendations"
          value={recommendations.length}
          tone="cat"
          delay={0}
        />
        <SummaryCard
          icon={<DollarSign className="h-5 w-5" />}
          label="Total Potential Savings"
          value={totalSavings}
          prefix="$"
          tone="ok"
          delay={0.06}
        />
        <SummaryCard
          icon={<TrendingUp className="h-5 w-5" />}
          label="Avg. Confidence"
          value={avgConfidence}
          suffix="%"
          tone="info"
          delay={0.12}
        />
        <SummaryCard
          icon={<Sparkles className="h-5 w-5" />}
          label="High Priority"
          value={highPriority}
          tone="crit"
          delay={0.18}
        />
      </div>

      {/* Live anomaly detection feed */}
      <div className="mb-6">
        <AnomalyMonitor limit={12} />
      </div>

      {/* Filters */}
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-ink-200" />
          <span className="text-xs font-medium text-ink-200">Category</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                cat === c ? 'bg-cat-yellow text-ink-900' : 'bg-ink-500/40 text-ink-100 hover:bg-ink-500/60'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="hidden h-5 w-px bg-white/10 lg:block" />
        <div className="flex flex-wrap items-center gap-2">
          {priorities.map((p) => (
            <button
              key={p}
              onClick={() => setPri(p)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                pri === p ? 'bg-cat-yellow text-ink-900' : 'bg-ink-500/40 text-ink-100 hover:bg-ink-500/60'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Recommendations grid */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-cat-yellow" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-500/50 text-ink-200">
            <Brain className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-semibold text-ink-50">No recommendations match these filters</h3>
          <p className="mt-1 text-sm text-ink-200">Adjust the category or priority to see more.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((r, i) => (
            <RecommendationCard key={r.id} rec={r} delay={i * 0.06} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}

function SummaryCard({
  icon, label, value, prefix = '', suffix = '', tone, delay,
}: {
  icon: React.ReactNode; label: string; value: number; prefix?: string; suffix?: string;
  tone: 'cat' | 'ok' | 'info' | 'crit'; delay: number;
}) {
  const color = tone === 'cat' ? 'text-cat-yellow' : tone === 'ok' ? 'text-ok' : tone === 'info' ? 'text-info' : 'text-crit';
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      whileHover={{ y: -2 }}
      className="card card-hover p-5"
    >
      <div className="flex items-center gap-2.5">
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.04] ${color}`}>
          {icon}
        </div>
        <span className="text-xs font-medium uppercase tracking-wider text-ink-200">{label}</span>
      </div>
      <div className={`mt-3 text-3xl font-bold ${color}`}>
        <AnimatedCounter value={value} prefix={prefix} suffix={suffix} />
      </div>
    </motion.div>
  );
}
