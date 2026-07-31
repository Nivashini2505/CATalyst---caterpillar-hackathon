import { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Loader2, AlertTriangle } from 'lucide-react';

export const SEV_TONE: Record<string, string> = {
  critical: 'bg-crit/15 text-crit border-crit/30',
  high: 'bg-warn/15 text-warn border-warn/30',
  medium: 'bg-info/15 text-info border-info/30',
  low: 'bg-ink-400/30 text-ink-100 border-white/10',
};

export function Badge({ tone = 'neutral', children, dot }: { tone?: string; children: ReactNode; dot?: boolean }) {
  const cls = SEV_TONE[tone] || 'bg-ink-400/30 text-ink-100 border-white/10';
  return (
    <span className={`chip border ${cls}`}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-soft" />}
      {children}
    </span>
  );
}

export function Card({ children, className = '', delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
      className={`card p-5 ${className}`}
    >
      {children}
    </motion.div>
  );
}

export function Loading({ label = 'Loading live predictions…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-ink-200">
      <Loader2 className="h-7 w-7 animate-spin text-cat-yellow" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-crit/20 bg-crit/[0.04] py-14 text-center">
      <AlertTriangle className="h-7 w-7 text-crit" />
      <div className="text-sm font-semibold text-ink-50">Couldn’t reach the ML backend</div>
      <div className="max-w-md text-xs text-ink-200">{message}</div>
      <div className="text-[11px] text-ink-300">Make sure the FastAPI backend is running on http://127.0.0.1:8000</div>
      {onRetry && <button onClick={onRetry} className="btn btn-ghost mt-1 text-xs">Retry</button>}
    </div>
  );
}

// Circular gauge (health / risk).
export function Gauge({ value, size = 128, label, tone }: { value: number; size?: number; label?: string; tone?: 'ok' | 'warn' | 'crit' }) {
  const t = tone || (value >= 80 ? 'ok' : value >= 60 ? 'warn' : 'crit');
  const color = t === 'ok' ? '#22C55E' : t === 'warn' ? '#F59E0B' : '#EF4444';
  const r = (size - 14) / 2;
  const circ = 2 * Math.PI * r;
  const off = circ * (1 - Math.max(0, Math.min(100, value)) / 100);
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.08)" strokeWidth={9} fill="none" />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={9} fill="none"
          strokeLinecap="round" strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }} animate={{ strokeDashoffset: off }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold text-white">{Math.round(value)}</span>
        {label && <span className="text-[10px] uppercase tracking-wider text-ink-200">{label}</span>}
      </div>
    </div>
  );
}

export function Stat({ label, value, tone = 'ink', hint }: { label: string; value: ReactNode; tone?: string; hint?: string }) {
  const color = tone === 'crit' ? 'text-crit' : tone === 'warn' ? 'text-warn'
    : tone === 'ok' ? 'text-ok' : tone === 'cat' ? 'text-cat-yellow' : 'text-white';
  return (
    <div className="rounded-xl border border-white/[0.06] bg-ink-500/40 p-4">
      <div className="text-[10px] font-medium uppercase tracking-wider text-ink-200">{label}</div>
      <div className={`mt-1.5 text-2xl font-bold ${color}`}>{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-ink-300">{hint}</div>}
    </div>
  );
}

// Plain-English explanation banner shown under every prediction.
export function Explain({ children }: { children: ReactNode }) {
  return (
    <div className="mt-4 flex gap-2.5 rounded-xl border border-cat-yellow/20 bg-cat-yellow/[0.05] p-3.5">
      <span className="mt-0.5 text-cat-yellow">💡</span>
      <p className="text-[13px] leading-relaxed text-ink-100">{children}</p>
    </div>
  );
}
