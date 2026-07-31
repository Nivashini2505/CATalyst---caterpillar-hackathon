import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Truck,
  Radio,
  Building2,
  HardHat,
  Brain,
  TrendingUp,
  Bot,
  Settings,
} from 'lucide-react';
import { motion } from 'framer-motion';

const nav = [
  { to: '/', label: 'Mission Control', icon: LayoutDashboard, end: true },
  { to: '/fleet', label: 'Fleet Intelligence', icon: Truck },
  { to: '/operations', label: 'Live Operations', icon: Radio },
  { to: '/sites', label: 'Sites', icon: Building2 },
  { to: '/workforce', label: 'Workforce', icon: HardHat },
  { to: '/decisions', label: 'Decision Center', icon: Brain },
  { to: '/forecast', label: 'Forecasting', icon: TrendingUp },
];

export function Sidebar({ open }: { open: boolean }) {
  return (
    <aside
      className={`fixed left-0 top-0 z-40 h-screen w-64 transform border-r border-white/[0.04] bg-ink-700 transition-transform duration-300 lg:translate-x-0 ${
        open ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="flex h-16 items-center gap-2.5 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat-yellow text-ink-900">
          <Truck className="h-5 w-5" strokeWidth={2.5} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-bold text-white">CAT RENTAL</div>
          <div className="text-[10px] font-medium tracking-wider text-cat-yellow">OPERATIONS BRAIN</div>
        </div>
      </div>

      <nav className="mt-2 flex flex-col gap-0.5 px-3">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive ? 'text-white' : 'text-ink-200 hover:text-ink-50 hover:bg-white/[0.03]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute inset-0 rounded-lg bg-cat-yellow/10"
                    transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                  />
                )}
                <item.icon className="relative z-10 h-[18px] w-[18px]" strokeWidth={2} />
                <span className="relative z-10">{item.label}</span>
                {isActive && (
                  <span className="relative z-10 ml-auto h-1.5 w-1.5 rounded-full bg-cat-yellow" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="absolute inset-x-0 bottom-0 px-3 pb-4">
        <div className="my-2 h-px bg-white/[0.04]" />
        <NavLink
          to="/copilot"
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-ink-200 transition-colors hover:bg-white/[0.03] hover:text-ink-50"
        >
          <Bot className="h-[18px] w-[18px]" strokeWidth={2} />
          AI Copilot
        </NavLink>
        <NavLink
          to="/settings"
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-ink-200 transition-colors hover:bg-white/[0.03] hover:text-ink-50"
        >
          <Settings className="h-[18px] w-[18px]" strokeWidth={2} />
          Settings
        </NavLink>
      </div>
    </aside>
  );
}
