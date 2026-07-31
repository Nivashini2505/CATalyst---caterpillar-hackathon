import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Truck, TrendingUp, ShieldAlert, Wrench, ArrowLeft } from 'lucide-react';

const NAV = [
  { to: '/demand', label: 'Demand Forecasting', icon: TrendingUp },
  { to: '/anomaly', label: 'Anomaly Detection', icon: ShieldAlert },
  { to: '/maintenance', label: 'Predictive Maintenance', icon: Wrench },
];

export function Shell({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const onLanding = loc.pathname === '/';
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-ink-700/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-5 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat-yellow text-ink-900">
              <Truck className="h-5 w-5" strokeWidth={2.5} />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-extrabold tracking-tight text-white">CAT-alyst</div>
              <div className="text-[10px] font-semibold tracking-wider text-cat-yellow">AI FLEET INTELLIGENCE</div>
            </div>
          </Link>

          {!onLanding && (
            <nav className="ml-4 hidden items-center gap-1 md:flex">
              {NAV.map((n) => {
                const active = loc.pathname === n.to;
                return (
                  <Link key={n.to} to={n.to}
                    className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                      active ? 'bg-cat-yellow/10 text-cat-yellow' : 'text-ink-200 hover:text-ink-50 hover:bg-white/[0.03]'
                    }`}>
                    <n.icon className="h-4 w-4" /> {n.label}
                  </Link>
                );
              })}
            </nav>
          )}

          <div className="ml-auto flex items-center gap-3">
            <span className="hidden items-center gap-1.5 text-[11px] text-ink-200 sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-ok animate-pulse-soft" /> Live ML backend
            </span>
            {!onLanding && (
              <Link to="/" className="btn btn-ghost text-xs">
                <ArrowLeft className="h-3.5 w-3.5" /> Home
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>

      <footer className="mx-auto max-w-7xl px-5 py-6 text-center text-[11px] text-ink-300">
        CAT-alyst ML demo · Demand Forecasting · Anomaly Detection · Predictive Maintenance ·
        predictions served live from the trained models
      </footer>
    </div>
  );
}
