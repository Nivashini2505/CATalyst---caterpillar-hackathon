import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Search, SlidersHorizontal, ArrowUpDown, Eye, Truck, Loader2 } from 'lucide-react';
import { fetchEquipment } from '@/services/api';

import { Badge, statusTone } from '@/components/ui/Badge';
import { RingGauge } from '@/components/ui/RingGauge';
import { PageContainer, PageHeader, EmptyState } from '@/components/ui/Page';

const categories = ['All', 'Excavator', 'Dozer', 'Loader', 'Grader', 'Truck', 'Compactor'];
const statusLabel: Record<string, string> = {
  working: 'Working', idle: 'Idle', critical: 'Critical', maintenance: 'Maintenance', transit: 'Transit',
};

type SortKey = 'name' | 'health' | 'idleHours' | 'rentalRemainingDays';

export function FleetPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortAsc, setSortAsc] = useState(true);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const data = await fetchEquipment();
        setEquipment(data);
      } catch (err) {
        console.error("Failed to fetch equipment", err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const filtered = useMemo(() => {
    let r = equipment.filter(
      (e) =>
        (category === 'All' || e.category === category) &&
        (e.name.toLowerCase().includes(query.toLowerCase()) ||
          e.site.toLowerCase().includes(query.toLowerCase()) ||
          e.operator.toLowerCase().includes(query.toLowerCase()))
    );
    r = [...r].sort((a, b) => {
      const v = sortAsc
        ? (a[sortKey] > b[sortKey] ? 1 : -1)
        : (a[sortKey] < b[sortKey] ? 1 : -1);
      return v;
    });
    return r;
  }, [equipment, query, category, sortKey, sortAsc]);

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortAsc(!sortAsc);
    else { setSortKey(k); setSortAsc(true); }
  };

  return (
    <PageContainer title="Fleet Intelligence">
      <PageHeader
        title="Fleet Intelligence"
        subtitle="Search, filter, and inspect your rental equipment across all sites."
      />

      <div className="card mb-5 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-200" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search equipment, site, or operator..."
              className="w-full rounded-lg border border-white/[0.06] bg-ink-500/40 py-2 pl-10 pr-4 text-sm text-ink-50 placeholder:text-ink-200 focus:border-cat-yellow/40 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2 overflow-x-auto scrollbar-thin">
            <SlidersHorizontal className="h-4 w-4 shrink-0 text-ink-200" />
            {categories.map((c) => (
              <button
                key={c}
                onClick={() => setCategory(c)}
                className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  category === c
                    ? 'bg-cat-yellow text-ink-900'
                    : 'bg-ink-500/40 text-ink-100 hover:bg-ink-500/60'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="h-8 w-8 animate-spin text-cat-yellow" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<Truck className="h-6 w-6" />}
            title="No equipment found"
            description="Try adjusting your search or filters."
          />
        </div>
      ) : (
        <>
          {/* Card grid view */}
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {filtered.map((eq, i) => (
              <motion.button
                key={eq.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                whileHover={{ y: -3 }}
                onClick={() => navigate(`/equipment/${eq.id}`)}
                className="card card-hover group overflow-hidden text-left"
              >
                <div className="relative h-32 overflow-hidden">
                  <img
                    src={eq.image}
                    alt={eq.name}
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    loading="lazy"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-ink-600 to-transparent" />
                  <div className="absolute right-3 top-3">
                    <Badge tone={statusTone(eq.status)} dot={eq.status === 'critical'}>
                      {statusLabel[eq.status]}
                    </Badge>
                  </div>
                </div>
                <div className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-white">{eq.name}</div>
                      <div className="text-[10px] text-ink-200">{eq.site} · {eq.operator}</div>
                    </div>
                    <RingGauge value={eq.health} size={42} stroke={4} tone={eq.health > 85 ? 'ok' : eq.health > 70 ? 'warn' : 'crit'} />
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <span className="text-ink-200">Idle <span className="text-ink-50 font-medium">{eq.idleHours}h</span></span>
                    <span className="text-ink-200">Rental <span className={`font-medium ${eq.rentalRemainingDays <= 6 ? 'text-crit' : 'text-ink-50'}`}>{eq.rentalRemainingDays}d</span></span>
                    <span className="inline-flex items-center gap-1 text-cat-yellow">
                      <Eye className="h-3 w-3" /> View
                    </span>
                  </div>
                </div>
              </motion.button>
            ))}
          </div>

          {/* Table view */}
          <div className="card overflow-hidden">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full min-w-[760px] text-left">
                <thead>
                  <tr className="border-b border-white/[0.04] text-[10px] uppercase tracking-wider text-ink-200">
                    <th className="px-5 py-3">
                      <SortBtn label="Equipment" active={sortKey === 'name'} asc={sortAsc} onClick={() => toggleSort('name')} />
                    </th>
                    <th className="px-3 py-3 font-medium">Site</th>
                    <th className="px-3 py-3 font-medium">Operator</th>
                    <th className="px-3 py-3">
                      <SortBtn label="Health" active={sortKey === 'health'} asc={sortAsc} onClick={() => toggleSort('health')} />
                    </th>
                    <th className="px-3 py-3">
                      <SortBtn label="Idle" active={sortKey === 'idleHours'} asc={sortAsc} onClick={() => toggleSort('idleHours')} />
                    </th>
                    <th className="px-3 py-3">
                      <SortBtn label="Rental" active={sortKey === 'rentalRemainingDays'} asc={sortAsc} onClick={() => toggleSort('rentalRemainingDays')} />
                    </th>
                    <th className="px-3 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((eq) => (
                    <tr
                      key={eq.id}
                      onClick={() => navigate(`/equipment/${eq.id}`)}
                      className="cursor-pointer border-b border-white/[0.03] transition-colors hover:bg-white/[0.02]"
                    >
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <img src={eq.image} alt={eq.name} className="h-8 w-10 rounded object-cover" loading="lazy" />
                          <div>
                            <div className="text-sm font-medium text-ink-50">{eq.name}</div>
                            <div className="text-[10px] text-ink-200">{eq.model}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-sm text-ink-100">{eq.site}</td>
                      <td className="px-3 py-3 text-sm text-ink-100">{eq.operator}</td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink-400">
                            <div
                              className={`h-full rounded-full ${eq.health > 85 ? 'bg-ok' : eq.health > 70 ? 'bg-warn' : 'bg-crit'}`}
                              style={{ width: `${eq.health}%` }}
                            />
                          </div>
                          <span className="text-xs text-ink-100">{eq.health}%</span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-sm">{eq.idleHours}h</td>
                      <td className="px-3 py-3 text-sm">{eq.rentalRemainingDays}d</td>
                      <td className="px-3 py-3">
                        <Badge tone={statusTone(eq.status)} dot={eq.status === 'critical'}>{statusLabel[eq.status]}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </PageContainer>
  );
}

function SortBtn({ label, active, asc, onClick }: { label: string; active: boolean; asc: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`inline-flex items-center gap-1 font-medium transition-colors ${active ? 'text-cat-yellow' : 'text-ink-200 hover:text-ink-100'}`}>
      {label}
      <ArrowUpDown className={`h-3 w-3 ${active && !asc ? 'rotate-180' : ''} transition-transform`} />
    </button>
  );
}
