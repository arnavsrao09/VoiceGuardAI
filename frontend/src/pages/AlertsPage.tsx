import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ShieldAlert, 
  AlertTriangle, 
  ShieldCheck, 
  Info, 
  Filter, 
  Download, 
  Clock, 
  CheckCircle,
  FileSpreadsheet,
  FileJson,
  ChevronDown
} from 'lucide-react';

interface AlertItem {
  id: string;
  session_id: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  trigger_reason: string;
  risk_score: number;
  created_at: string;
  acknowledged_at: string | null;
  status: 'active' | 'acknowledged';
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filterSev, setFilterSev] = useState<string>('all');
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/v1/alerts');
        if (res.ok) {
          const data = await res.json();
          setAlerts(data.map((a: any) => ({
            id: a.id,
            session_id: `#${String(a.session_id).slice(0, 5)}`,
            severity: a.severity.toLowerCase(),
            trigger_reason: a.trigger_reason,
            risk_score: a.risk_score,
            created_at: a.created_at,
            acknowledged_at: a.acknowledged_at || null,
            status: a.acknowledged_at ? 'acknowledged' : 'active',
          })));
        }
      } catch (err) {
        console.error('Failed to fetch alerts:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleAcknowledge = async (id: string) => {
    const nowIso = new Date().toISOString();
    // Optimistically update timestamp and status immediately
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id
          ? { ...a, acknowledged_at: nowIso, status: 'acknowledged' }
          : a
      )
    );

    try {
      const res = await fetch(`http://localhost:8000/api/v1/alerts/${id}/acknowledge`, {
        method: 'POST',
      });
      if (res.ok) {
        const updated = await res.json();
        setAlerts((prev) =>
          prev.map((a) =>
            a.id === id
              ? {
                  ...a,
                  acknowledged_at: updated.acknowledged_at || nowIso,
                  status: 'acknowledged',
                }
              : a
          )
        );
      }
    } catch (err) {
      console.error('Failed to acknowledge alert in database:', err);
    }
  };

  const filteredAlerts = alerts.filter(
    (a) => filterSev === 'all' || a.severity === filterSev
  );

  const exportSpreadsheet = (dataToExport: AlertItem[]) => {
    const headers = [
      'Alert ID',
      'Session ID',
      'Severity',
      'Risk Score',
      'Risk Percentage',
      'Trigger Reason',
      'Status',
      'Created At (UTC)',
      'Created At (IST)',
      'Acknowledged At (IST)',
    ];

    const rows = dataToExport.map((a) => {
      let istTime = '—';
      try {
        istTime = new Date(a.created_at).toLocaleString('en-IN', {
          timeZone: 'Asia/Kolkata',
          year: 'numeric',
          month: 'short',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        }) + ' IST';
      } catch {
        istTime = a.created_at;
      }

      let ackIstTime = 'Pending';
      if (a.acknowledged_at) {
        try {
          ackIstTime = new Date(a.acknowledged_at).toLocaleString('en-IN', {
            timeZone: 'Asia/Kolkata',
            year: 'numeric',
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true,
          }) + ' IST';
        } catch {
          ackIstTime = a.acknowledged_at;
        }
      }

      return [
        a.id,
        a.session_id,
        a.severity.toUpperCase(),
        typeof a.risk_score === 'number' ? a.risk_score.toFixed(4) : a.risk_score,
        typeof a.risk_score === 'number' ? `${(a.risk_score * 100).toFixed(1)}%` : '—',
        a.trigger_reason,
        a.acknowledged_at ? 'ACKNOWLEDGED' : 'ACTIVE',
        a.created_at,
        istTime,
        ackIstTime,
      ];
    });

    const escapeCsv = (val: any) => {
      if (val === null || val === undefined) return '';
      const str = String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const csvString = '\uFEFF' + [
      headers.join(','),
      ...rows.map((row) => row.map(escapeCsv).join(',')),
    ].join('\r\n');

    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `voiceguard_audit_log_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  const exportJson = (dataToExport: AlertItem[]) => {
    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `voiceguard_audit_log_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  const sevBadge = (sev: string) => {
    switch (sev) {
      case 'critical':
        return { label: 'CRITICAL', color: 'var(--color-risk-critical)', bg: 'rgba(239,68,68,0.12)', icon: ShieldAlert };
      case 'high':
        return { label: 'HIGH', color: 'var(--color-risk-high)', bg: 'rgba(249,115,22,0.12)', icon: AlertTriangle };
      case 'medium':
        return { label: 'MEDIUM', color: 'var(--color-risk-medium)', bg: 'rgba(245,197,66,0.12)', icon: Info };
      default:
        return { label: 'LOW', color: 'var(--color-risk-low)', bg: 'rgba(0,229,200,0.12)', icon: ShieldCheck };
    }
  };

  return (
    <div className="min-h-screen pt-24 pb-12 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-sentinel-text)] flex items-center gap-2.5">
              <ShieldAlert className="w-6 h-6 text-[var(--color-risk-critical)]" />
              Detection Alert History
            </h1>
            <p className="text-sm text-[var(--color-sentinel-text-muted)] mt-1">
              Audit trail of voice cloning alerts, deepfake probability spikes, and mid-call identity drifts.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative" ref={exportMenuRef}>
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                disabled={alerts.length === 0}
                className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition-all ${
                  alerts.length === 0
                    ? 'border-[var(--color-sentinel-border)] text-[var(--color-sentinel-text-dim)] cursor-not-allowed opacity-60'
                    : showExportMenu
                    ? 'border-[var(--color-accent-primary)] text-[var(--color-accent-primary)] bg-[rgba(0,229,200,0.08)] shadow-md'
                    : 'border-[var(--color-sentinel-border)] text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:border-[var(--color-sentinel-text-dim)]'
                }`}
              >
                <Download className="w-4 h-4" />
                Export Audit Log
                <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${showExportMenu ? 'rotate-180 text-[var(--color-accent-primary)]' : ''}`} />
              </button>

              <AnimatePresence>
                {showExportMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: 8, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.96 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 mt-2 w-64 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface-2)] p-2 shadow-2xl z-50 backdrop-blur-xl"
                  >
                    <div className="px-3 py-2 border-b border-[var(--color-sentinel-border)] mb-1">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-sentinel-text-dim)]">
                        Select Export Format
                      </p>
                      <p className="text-xs text-[var(--color-sentinel-text-muted)]">
                        {filterSev !== 'all' ? `${filteredAlerts.length} filtered alerts` : `${alerts.length} total alerts`}
                      </p>
                    </div>

                    <button
                      onClick={() => exportSpreadsheet(filterSev !== 'all' ? filteredAlerts : alerts)}
                      className="w-full flex items-center gap-3 p-2.5 rounded-xl hover:bg-[var(--color-sentinel-surface-3)] transition-colors text-left group cursor-pointer"
                    >
                      <div className="w-8 h-8 rounded-lg bg-[rgba(16,185,129,0.15)] flex items-center justify-center shrink-0 border border-[rgba(16,185,129,0.3)]">
                        <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-semibold text-[var(--color-sentinel-text)] group-hover:text-emerald-400 transition-colors">
                            Spreadsheet (.csv)
                          </p>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold">
                            CSV
                          </span>
                        </div>
                        <p className="text-[10px] text-[var(--color-sentinel-text-dim)]">
                          Excel & Google Sheets ready
                        </p>
                      </div>
                    </button>

                    <button
                      onClick={() => exportJson(filterSev !== 'all' ? filteredAlerts : alerts)}
                      className="w-full flex items-center gap-3 p-2.5 rounded-xl hover:bg-[var(--color-sentinel-surface-3)] transition-colors text-left group mt-1 cursor-pointer"
                    >
                      <div className="w-8 h-8 rounded-lg bg-[rgba(0,229,200,0.12)] flex items-center justify-center shrink-0 border border-[rgba(0,229,200,0.25)]">
                        <FileJson className="w-4 h-4 text-[var(--color-accent-primary)]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-semibold text-[var(--color-sentinel-text)] group-hover:text-[var(--color-accent-primary)] transition-colors">
                            JSON Document (.json)
                          </p>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-[rgba(0,229,200,0.15)] text-[var(--color-accent-primary)] font-mono font-bold">
                            JSON
                          </span>
                        </div>
                        <p className="text-[10px] text-[var(--color-sentinel-text-dim)]">
                          Raw structured audit payload
                        </p>
                      </div>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
          <span className="text-xs font-semibold text-[var(--color-sentinel-text-dim)] flex items-center gap-1 mr-2">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </span>
          {['all', 'critical', 'high', 'medium', 'low'].map((sev) => (
            <button
              key={sev}
              onClick={() => setFilterSev(sev)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold uppercase transition-all ${
                filterSev === sev
                  ? 'bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)]'
                  : 'bg-[var(--color-sentinel-surface)] text-[var(--color-sentinel-text-muted)] border border-[var(--color-sentinel-border)] hover:border-[var(--color-sentinel-text-dim)]'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        {/* Alert List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-3 border-[var(--color-accent-primary)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div className="text-center py-16">
            <ShieldCheck className="w-12 h-12 text-[var(--color-sentinel-text-dim)] mx-auto mb-4" />
            <h3 className="text-lg font-bold text-[var(--color-sentinel-text)] mb-2">No Alerts Found</h3>
            <p className="text-sm text-[var(--color-sentinel-text-muted)]">
              Your detection history is clean based on the current filters.
            </p>
          </div>
        ) : (
        <div className="flex flex-col gap-3">
          {filteredAlerts.map((a) => {
            const badge = sevBadge(a.severity);
            const Icon = badge.icon;
            return (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 mt-0.5" style={{ background: badge.bg }}>
                    <Icon className="w-5 h-5" style={{ color: badge.color }} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: badge.bg, color: badge.color }}>
                        {badge.label}
                      </span>
                      <span className="text-xs font-mono text-[var(--color-sentinel-text-dim)]">Session {a.session_id}</span>
                      <span className="text-xs font-bold text-[var(--color-sentinel-text-muted)]">Risk Score: {a.risk_score.toFixed(2)}</span>
                    </div>
                    <p className="text-sm font-semibold text-[var(--color-sentinel-text)]">{a.trigger_reason}</p>
                    <p className="text-xs text-[var(--color-sentinel-text-dim)] flex items-center gap-1 mt-1">
                      <Clock className="w-3 h-3" /> {new Date(a.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                  {a.status === 'active' ? (
                    <button
                      onClick={() => handleAcknowledge(a.id)}
                      className="px-4 py-2 rounded-xl bg-[var(--color-sentinel-surface-3)] border border-[var(--color-sentinel-border)] text-xs font-semibold text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:border-[var(--color-sentinel-text-dim)] transition-all"
                    >
                      Acknowledge Alert
                    </button>
                  ) : (
                    <span className="flex items-center gap-1 text-xs font-semibold text-[var(--color-risk-low)]">
                      <CheckCircle className="w-4 h-4" /> Acknowledged
                    </span>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
        )}
      </div>
    </div>
  );
}
