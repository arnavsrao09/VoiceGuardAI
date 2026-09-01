import { useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldAlert, AlertTriangle, ShieldCheck, Info, Filter, Download, Clock, CheckCircle } from 'lucide-react';

interface AlertItem {
  id: string;
  session_id: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  trigger_reason: string;
  risk_score: number;
  created_at: string;
  status: 'active' | 'acknowledged';
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([
    {
      id: 'alt-801a9f',
      session_id: '#4358c',
      severity: 'critical',
      trigger_reason: 'High deepfake probability detected (0.91) via AASIST model',
      risk_score: 0.88,
      created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      status: 'active',
    },
    {
      id: 'alt-712b3e',
      session_id: '#4358c',
      severity: 'high',
      trigger_reason: 'Speaker identity change detected mid-call via ECAPA-TDNN drift tracking',
      risk_score: 0.74,
      created_at: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
      status: 'active',
    },
    {
      id: 'alt-542c1d',
      session_id: '#1039',
      severity: 'medium',
      trigger_reason: 'Unnatural pitch contour & low spectral flatness detected by prosody analyzer',
      risk_score: 0.52,
      created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      status: 'acknowledged',
    },
    {
      id: 'alt-211d0a',
      session_id: '#1038',
      severity: 'low',
      trigger_reason: 'Routine monitoring session completed — low impersonation risk',
      risk_score: 0.14,
      created_at: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
      status: 'acknowledged',
    },
  ]);

  const [filterSev, setFilterSev] = useState<string>('all');

  const handleAcknowledge = (id: string) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status: 'acknowledged' } : a))
    );
  };

  const filteredAlerts = alerts.filter(
    (a) => filterSev === 'all' || a.severity === filterSev
  );

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
            <button
              onClick={() => {
                const blob = new Blob([JSON.stringify(alerts, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `voiceguard_alerts_${Date.now()}.json`;
                a.click();
              }}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--color-sentinel-border)] text-sm font-medium text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:border-[var(--color-sentinel-text-dim)] transition-all"
            >
              <Download className="w-4 h-4" />
              Export Audit Log
            </button>
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
      </div>
    </div>
  );
}
