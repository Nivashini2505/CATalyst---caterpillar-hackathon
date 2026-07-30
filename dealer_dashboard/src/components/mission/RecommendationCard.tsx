import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X, Sparkles, TrendingUp, ArrowRight, Brain } from 'lucide-react';

import { Badge, priorityTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export interface Recommendation {
  id: string;
  equipment: string;
  equipmentId: string;
  recommendation: string;
  reason: string;
  savings: number;
  confidence: number;
  priority: 'high' | 'medium' | 'low';
  category: 'Relocation' | 'Maintenance' | 'Rental' | 'Utilization' | 'Security' | string;
}

export function RecommendationCard({
  rec,
  delay = 0,
  compact = false,
}: {
  rec: Recommendation;
  delay?: number;
  compact?: boolean;
}) {
  const [state, setState] = useState<'pending' | 'approved' | 'rejected'>('pending');

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -2 }}
      className={`card card-hover relative overflow-hidden ${
        state === 'approved' ? 'border-ok/30' : state === 'rejected' ? 'border-crit/20 opacity-60' : ''
      }`}
    >
      <div className="absolute left-0 top-0 h-full w-1 bg-cat-yellow/40" />
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cat-yellow/10 text-cat-yellow">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold text-white">{rec.equipment}</div>
              <div className="text-xs text-ink-200">{rec.category}</div>
            </div>
          </div>
          <Badge tone={priorityTone(rec.priority)} dot>
            {rec.priority} priority
          </Badge>
        </div>

        <div className="mt-4 rounded-lg border border-cat-yellow/15 bg-cat-yellow/[0.04] p-3">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-cat-yellow">
            <ArrowRight className="h-3 w-3" />
            Recommendation
          </div>
          <div className="mt-1 text-sm font-semibold text-white">{rec.recommendation}</div>
        </div>

        {!compact && (
          <div className="mt-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-200">
              Business Reason
            </div>
            <p className="mt-1 text-sm leading-relaxed text-ink-100">{rec.reason}</p>
          </div>
        )}

        <div className="mt-4 grid grid-cols-3 gap-2">
          <Metric label="Est. Savings" value={`$${rec.savings.toLocaleString()}`} tone="cat" />
          <Metric label="Confidence" value={`${rec.confidence}%`} tone="ok" />
          <Metric label="Priority" value={rec.priority} tone={rec.priority === 'high' ? 'crit' : rec.priority === 'medium' ? 'warn' : 'info'} />
        </div>

        <div className="mt-4 flex items-center gap-2">
          <AnimatePresence mode="wait">
            {state === 'pending' && (
              <motion.div
                key="pending"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex w-full gap-2"
              >
                <Button variant="success" size="sm" className="flex-1" onClick={() => setState('approved')}>
                  <Check className="h-4 w-4" />
                  Approve
                </Button>
                <Button variant="danger" size="sm" className="flex-1" onClick={() => setState('rejected')}>
                  <X className="h-4 w-4" />
                  Reject
                </Button>
              </motion.div>
            )}
            {state === 'approved' && (
              <motion.div
                key="approved"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-ok/15 py-2 text-sm font-medium text-ok"
              >
                <Check className="h-4 w-4" />
                Approved — action queued
              </motion.div>
            )}
            {state === 'rejected' && (
              <motion.div
                key="rejected"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-crit/15 py-2 text-sm font-medium text-crit"
              >
                <X className="h-4 w-4" />
                Rejected
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: 'cat' | 'ok' | 'crit' | 'warn' | 'info' }) {
  const color = tone === 'cat' ? 'text-cat-yellow' : tone === 'ok' ? 'text-ok' : tone === 'crit' ? 'text-crit' : tone === 'warn' ? 'text-warn' : 'text-info';
  return (
    <div className="rounded-lg bg-ink-500/40 p-2.5 text-center">
      <div className="text-[9px] font-medium uppercase tracking-wider text-ink-200">{label}</div>
      <div className={`mt-0.5 text-sm font-bold ${color}`}>{value}</div>
    </div>
  );
}

export function DecisionCenterSection({
  recs,
  title = 'AI Decision Center',
  subtitle = 'Prioritized recommendations ready for your approval',
  limit,
}: {
  recs: Recommendation[];
  title?: string;
  subtitle?: string;
  limit?: number;
}) {
  const shown = limit ? recs.slice(0, limit) : recs;
  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat-yellow/10 text-cat-yellow">
            <Brain className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">{title}</h2>
            <p className="text-xs text-ink-200">{subtitle}</p>
          </div>
        </div>
        <Badge tone="cat">
          <TrendingUp className="h-3 w-3" />
          {recs.length} recommendations
        </Badge>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((r, i) => (
          <RecommendationCard key={r.id} rec={r} delay={i * 0.06} />
        ))}
      </div>
    </section>
  );
}
