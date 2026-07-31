import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  FileText, DollarSign, AlertTriangle, Clock, Activity, Download, FileSpreadsheet, FileBarChart, Loader2,
} from 'lucide-react';
import { fetchReports } from '@/services/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { PageContainer, PageHeader } from '@/components/ui/Page';

const tooltipStyle = {
  backgroundColor: '#1B1D20', border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '0.75rem', fontSize: '0.75rem', color: '#C7CCD4',
};

// ---- CSV export helpers (real client-side download) ----
function toCSV(rows: any[]): string {
  if (!rows || !rows.length) return '';
  const headers = Object.keys(rows[0]);
  const esc = (v: any) => {
    const s = String(v ?? '');
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [headers.join(','), ...rows.map((r) => headers.map((h) => esc(r[h])).join(','))].join('\n');
}
function downloadCSV(filename: string, csv: string) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ReportsPage() {
  const [reports, setReports] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchReports();
        setReports(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const tables = reports?.tables || {};
  const cards = reports?.cards || {};
  const period = reports?.period || '—';

  const exportAll = () => {
    const sections: [string, any[]][] = [
      ['Revenue Trend ($K)', tables.revenueTrend],
      ['Downtime (hours)', tables.downtimeData],
      ['Idle Analysis', tables.idleAnalysis],
      ['Utilization (%)', tables.utilizationTrend],
      ['Rental Trends', tables.rentalTrends],
    ];
    const parts = [`CAT-alyst Operations Report,Period: ${period}`, ''];
    for (const [title, rows] of sections) {
      parts.push(title, toCSV(rows || []), '');
    }
    downloadCSV('catalyst_operations_report.csv', parts.join('\n'));
  };
  const exportPDF = () => window.print();

  return (
    <PageContainer title="Reports">
      {/* Print styling: hide chrome so a Print-to-PDF shows only the report. */}
      <style>{`@media print {
        aside, header, .no-print { display: none !important; }
        main { margin: 0 !important; padding: 0 !important; }
      }`}</style>

      <PageHeader
        title="Reports"
        subtitle={`Operational reports across your fleet · Period ${period} · generated from live data`}
      />
      {loading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-8 w-8 animate-spin text-cat-yellow" /></div>
      ) : (
      <>
      {/* Report summary cards - real figures */}
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ReportCard
          icon={<DollarSign className="h-5 w-5" />} tone="cat" delay={0}
          title="Revenue Report" period={period}
          metric={`$${(cards.revenue?.total ?? 0).toLocaleString()}K`}
          sub={`avg $${(cards.revenue?.avgMonthly ?? 0).toLocaleString()}K/mo · best ${cards.revenue?.bestMonth ?? '—'}`}
          onExport={() => downloadCSV('revenue_report.csv', toCSV(tables.revenueTrend || []))}
        />
        <ReportCard
          icon={<AlertTriangle className="h-5 w-5" />} tone="crit" delay={0.06}
          title="Downtime Report" period={period}
          metric={`${cards.downtime?.unplannedPct ?? 0}%`}
          sub={`${cards.downtime?.unplanned ?? 0} unplanned vs ${cards.downtime?.scheduled ?? 0} scheduled units`}
          onExport={() => downloadCSV('downtime_report.csv', toCSV(tables.downtimeData || []))}
        />
        <ReportCard
          icon={<Clock className="h-5 w-5" />} tone="warn" delay={0.12}
          title="Idle Analysis" period={period}
          metric={`$${(cards.idle?.totalCost ?? 0).toLocaleString()}`}
          sub={`${(cards.idle?.totalHours ?? 0).toLocaleString()} idle hrs · worst: ${cards.idle?.worstCategory ?? '—'}`}
          onExport={() => downloadCSV('idle_analysis.csv', toCSV(tables.idleAnalysis || []))}
        />
        <ReportCard
          icon={<Activity className="h-5 w-5" />} tone="info" delay={0.18}
          title="Utilization Report" period={period}
          metric={`${cards.utilization?.avg ?? 0}%`}
          sub={`peak ${cards.utilization?.peak ?? 0}% · current ${cards.utilization?.current ?? 0}%`}
          onExport={() => downloadCSV('utilization_report.csv', toCSV(tables.utilizationTrend || []))}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Revenue (Monthly, $K)" subtitle="Actual vs target" delay={0}>
          <BarChart data={tables.revenueTrend || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="month" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="target" fill="#3A3F47" radius={[4, 4, 0, 0]} />
            <Bar dataKey="revenue" fill="#FFCD11" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Downtime (Machines)" subtitle="Scheduled vs unplanned by week" delay={0.06}>
          <BarChart data={tables.downtimeData || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="week" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="scheduled" stackId="a" fill="#3B82F6" radius={[0, 0, 0, 0]} />
            <Bar dataKey="unplanned" stackId="a" fill="#EF4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Idle Analysis" subtitle="Idle hours by equipment category" delay={0.12}>
          <BarChart data={tables.idleAnalysis || []} layout="vertical" margin={{ top: 10, right: 10, left: 20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
            <XAxis type="number" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis dataKey="category" type="category" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} width={80} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Bar dataKey="hours" fill="#F59E0B" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Utilization" subtitle="Weekly utilization %" delay={0.18}>
          <BarChart data={tables.utilizationTrend || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="week" tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#8A93A1', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Bar dataKey="utilization" fill="#22C55E" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
      </div>

      {/* Export bar */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="no-print card mt-6 flex flex-col items-center justify-between gap-4 p-5 sm:flex-row"
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cat-yellow/10 text-cat-yellow">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Export Operations Report</div>
            <div className="text-xs text-ink-200">Consolidated report of all metrics above ({period})</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={exportAll}>
            <FileSpreadsheet className="h-4 w-4" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={exportPDF}>
            <FileBarChart className="h-4 w-4" />
            PDF
          </Button>
          <Button size="sm" onClick={exportAll}>
            <Download className="h-4 w-4" />
            Export All
          </Button>
        </div>
      </motion.div>
      </>
      )}
    </PageContainer>
  );
}

function ReportCard({
  icon, title, metric, sub, tone, delay, period, onExport,
}: {
  icon: React.ReactNode; title: string; metric: string; sub: string;
  tone: 'cat' | 'crit' | 'warn' | 'info'; delay: number; period: string; onExport: () => void;
}) {
  const color = tone === 'cat' ? 'text-cat-yellow bg-cat-yellow/10'
    : tone === 'crit' ? 'text-crit bg-crit/10'
    : tone === 'warn' ? 'text-warn bg-warn/10' : 'text-info bg-info/10';
  const valueColor = tone === 'cat' ? 'text-cat-yellow'
    : tone === 'crit' ? 'text-crit' : tone === 'warn' ? 'text-warn' : 'text-info';
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      whileHover={{ y: -3 }}
      className="card card-hover p-5"
    >
      <div className="flex items-center justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${color}`}>{icon}</div>
        <Badge tone="neutral">{period}</Badge>
      </div>
      <h3 className="mt-3 text-sm font-semibold text-white">{title}</h3>
      <div className={`mt-1 text-2xl font-bold ${valueColor}`}>{metric}</div>
      <p className="mt-1 text-xs leading-relaxed text-ink-200">{sub}</p>
      <button
        onClick={onExport}
        className="no-print mt-3 inline-flex items-center gap-1 text-xs font-medium text-cat-yellow hover:underline"
      >
        <Download className="h-3 w-3" /> Export CSV
      </button>
    </motion.div>
  );
}

function ChartCard({
  title, subtitle, children, delay,
}: {
  title: string; subtitle: string; children: React.ReactNode; delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="card p-5"
    >
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <p className="text-xs text-ink-200">{subtitle}</p>
      </div>
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          {children as any}
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
