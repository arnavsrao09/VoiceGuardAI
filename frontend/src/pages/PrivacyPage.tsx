import { AlertTriangle, CalendarDays, Clock, Database, Download, Shield, ShieldCheck, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';

interface Inventory {
  sessions: number;
  profiles: number;
  telemetry: number;
  alerts: number;
}

interface RetentionConfig {
  session_ttl_days: number;
  telemetry_ttl_days: number;
  embedding_ttl_days: number;
  alert_ttl_days: number;
}

interface AuditEntry {
  id: string;
  event_type: string;
  details: any;
  created_at: string;
}

export default function PrivacyPage() {
  const [privacyMode, setPrivacyMode] = useState(true);
  const [inferenceMode, setInferenceMode] = useState('EDGE');
  const [inventory, setInventory] = useState<Inventory>({ sessions: 0, profiles: 0, telemetry: 0, alerts: 0 });
  const [config, setConfig] = useState<RetentionConfig>({
    session_ttl_days: 30,
    telemetry_ttl_days: 30,
    embedding_ttl_days: 90,
    alert_ttl_days: 90
  });
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [erasureConfirm, setErasureConfirm] = useState(false);
  const [erasing, setErasing] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statusRes, auditRes] = await Promise.all([
        apiFetch('/privacy/status'),
        apiFetch('/privacy/audit-log?limit=10')
      ]);
      setPrivacyMode(statusRes.privacy_mode);
      setInferenceMode(statusRes.inference_mode);
      setConfig(statusRes.retention_config);
      setInventory(statusRes.inventory);
      setAuditLog(auditRes);
    } catch (err) {
      console.error('Failed to load privacy data', err);
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    try {
      setSaving(true);
      await apiFetch('/privacy/retention', {
        method: 'PUT',
        body: JSON.stringify({ ...config, inference_mode: inferenceMode })
      });
      fetchData(); // Refresh log
    } catch (err) {
      console.error('Failed to save config', err);
    } finally {
      setSaving(false);
    }
  };

  const triggerManualPurge = async () => {
    try {
      await apiFetch('/privacy/purge', { method: 'POST' });
      fetchData(); // Refresh inventory and log
    } catch (err) {
      console.error('Failed to trigger manual purge', err);
    }
  };

  const handleErasure = async () => {
    try {
      setErasing(true);
      await apiFetch('/privacy/erasure', { method: 'POST' });
      setErasureConfirm(false);
      fetchData();
    } catch (err) {
      console.error('Failed to erase data', err);
    } finally {
      setErasing(false);
    }
  };

  const handleExportCompliance = async () => {
    try {
      const data = await apiFetch('/privacy/compliance-report');
      const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute("href", jsonStr);
      downloadAnchor.setAttribute("download", `VoiceGuardAI_Compliance_Report_${Date.now()}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      fetchData(); // Refresh log
    } catch (err) {
      console.error('Failed to export compliance report:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen pt-10 pb-12 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-accent-primary)]"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-10 pb-12 px-4 sm:px-6">
      <div className="max-w-[1440px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-sentinel-text)] flex items-center gap-2.5">
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
              Privacy & Compliance
            </h1>
            <p className="text-sm text-[var(--color-sentinel-text-muted)] mt-1">
              Manage data retention, review audit logs, and configure DPDP/GDPR compliance.
            </p>
          </div>
          <button
            onClick={handleExportCompliance}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-sm font-bold hover:bg-emerald-500/20 transition-all shadow-sm"
          >
            <Download className="w-4 h-4" />
            Export Compliance Report
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Status Hero */}
          <div className="col-span-1 lg:col-span-2 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6 relative overflow-hidden">
            <div className="absolute -right-10 -top-10 w-40 h-40 bg-emerald-500/10 rounded-full blur-3xl" />
            <h2 className="text-lg font-bold text-[var(--color-sentinel-text)] mb-4">Inference Mode</h2>
            
            <div className="flex flex-wrap gap-4 mb-4 relative z-10">
              <button
                onClick={() => setInferenceMode('ON_DEVICE')}
                className={`px-4 py-2 rounded-full text-sm font-bold border transition-all ${
                  inferenceMode === 'ON_DEVICE'
                    ? 'bg-[var(--color-accent-primary-dim)] text-[var(--color-accent-primary)] border-[var(--color-accent-primary)]'
                    : 'bg-transparent text-gray-400 border-gray-700 hover:border-gray-500'
                }`}
              >
                On-Device
              </button>
              <button
                onClick={() => setInferenceMode('EDGE')}
                className={`px-4 py-2 rounded-full text-sm font-bold border transition-all ${
                  inferenceMode === 'EDGE'
                    ? 'bg-blue-500/10 text-blue-400 border-blue-500'
                    : 'bg-transparent text-gray-400 border-gray-700 hover:border-gray-500'
                }`}
              >
                Edge Processing
              </button>
              <button
                onClick={() => setInferenceMode('CLOUD')}
                className={`px-4 py-2 rounded-full text-sm font-bold border transition-all ${
                  inferenceMode === 'CLOUD'
                    ? 'bg-purple-500/10 text-purple-400 border-purple-500'
                    : 'bg-transparent text-gray-400 border-gray-700 hover:border-gray-500'
                }`}
              >
                Cloud Audit
              </button>
            </div>
            <p className="text-sm text-gray-400 max-w-xl">
              {inferenceMode === 'ON_DEVICE' && "Absolute privacy. Audio never leaves the client device. Only encrypted feature vectors are transmitted."}
              {inferenceMode === 'EDGE' && "Balanced privacy. Audio is processed transiently in RAM at the edge node and immediately purged. Zero persistence."}
              {inferenceMode === 'CLOUD' && "Full auditability. Audio and telemetry are stored securely in the cloud based on your retention policy."}
            </p>
            {privacyMode && (
               <div className="mt-4 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                 <Shield className="w-3.5 h-3.5" />
                 RAM-Only Persistence Active
               </div>
            )}
          </div>

          {/* Data Inventory */}
          <div className="col-span-1 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6">
             <h2 className="text-lg font-bold text-[var(--color-sentinel-text)] mb-4 flex items-center gap-2">
               <Database className="w-5 h-5 text-indigo-400" />
               Data Inventory
             </h2>
             <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Stored Sessions</span>
                  <span className="text-sm font-bold text-gray-200">{inventory.sessions}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Voice Profiles</span>
                  <span className="text-sm font-bold text-gray-200">{inventory.profiles}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Telemetry Records</span>
                  <span className="text-sm font-bold text-gray-200">{inventory.telemetry}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Alerts</span>
                  <span className="text-sm font-bold text-gray-200">{inventory.alerts}</span>
                </div>
             </div>
             <button
               onClick={triggerManualPurge}
               className="mt-6 w-full py-2 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] text-xs font-bold text-gray-300 hover:bg-gray-800 transition"
             >
               Trigger Manual Purge
             </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Retention Sliders */}
          <div className="col-span-1 lg:col-span-2 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6">
            <div className="flex justify-between items-center mb-6">
               <h2 className="text-lg font-bold text-[var(--color-sentinel-text)] flex items-center gap-2">
                 <Clock className="w-5 h-5 text-blue-400" />
                 Data Retention Policy (TTL)
               </h2>
               <button
                 onClick={saveConfig}
                 disabled={saving}
                 className="px-4 py-1.5 rounded-lg bg-[var(--color-accent-primary)] text-black text-sm font-bold shadow-lg shadow-[var(--color-accent-primary-glow)] hover:scale-105 transition disabled:opacity-50"
               >
                 {saving ? 'Saving...' : 'Save Policy'}
               </button>
            </div>

            <div className="space-y-6">
              {[
                { label: 'Detection Sessions (Days)', key: 'session_ttl_days', color: 'blue', max: 365 },
                { label: 'Risk Telemetry (Days)', key: 'telemetry_ttl_days', color: 'indigo', max: 365 },
                { label: 'Alerts (Days)', key: 'alert_ttl_days', color: 'amber', max: 365 },
                { label: 'Voice Profiles / Embeddings (Days)', key: 'embedding_ttl_days', color: 'emerald', max: 730 },
              ].map((item) => (
                <div key={item.key}>
                  <div className="flex justify-between text-xs font-semibold mb-2">
                    <span className="text-gray-300">{item.label}</span>
                    <span className={`text-${item.color}-400`}>{config[item.key as keyof RetentionConfig]} Days</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max={item.max}
                    step="1"
                    value={config[item.key as keyof RetentionConfig]}
                    onChange={(e) => setConfig({ ...config, [item.key]: parseInt(e.target.value) })}
                    className="w-full cursor-pointer"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Right to Erasure */}
          <div className="col-span-1 rounded-2xl border border-red-500/20 bg-[var(--color-sentinel-surface)] p-6 relative overflow-hidden">
            <div className="absolute right-0 top-0 w-32 h-32 bg-red-500/5 rounded-bl-[100px] pointer-events-none" />
            <h2 className="text-lg font-bold text-red-400 mb-2 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" />
              Right to Erasure
            </h2>
            <p className="text-xs text-gray-400 mb-6 leading-relaxed">
              Permanently delete all sessions, telemetry, profiles, and alerts for this organization. This action cannot be undone and complies with GDPR Article 17 and DPDP Section 12.
            </p>

            {erasureConfirm ? (
               <div className="space-y-3">
                 <p className="text-sm font-bold text-red-400">Are you absolutely sure?</p>
                 <div className="flex gap-2">
                   <button onClick={handleErasure} disabled={erasing} className="flex-1 py-2 bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg text-sm font-bold hover:bg-red-500/30 transition">
                     {erasing ? 'Erasing...' : 'Yes, Delete All'}
                   </button>
                   <button onClick={() => setErasureConfirm(false)} className="flex-1 py-2 bg-[var(--color-sentinel-surface-2)] text-gray-300 rounded-lg text-sm font-bold hover:bg-gray-800 transition">
                     Cancel
                   </button>
                 </div>
               </div>
            ) : (
               <button
                 onClick={() => setErasureConfirm(true)}
                 className="w-full py-2.5 rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 text-sm font-bold hover:bg-red-500/20 transition-all flex items-center justify-center gap-2"
               >
                 <Trash2 className="w-4 h-4" />
                 Initiate Full Erasure
               </button>
            )}
          </div>
        </div>

        {/* Audit Log */}
        <div className="mt-6 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6">
           <h2 className="text-lg font-bold text-[var(--color-sentinel-text)] mb-6 flex items-center gap-2">
             <CalendarDays className="w-5 h-5 text-[var(--color-accent-purple)]" />
             Privacy Audit Log
           </h2>
           
           <div className="space-y-3">
             {auditLog.length === 0 ? (
               <p className="text-sm text-gray-500">No recent privacy events.</p>
             ) : (
               auditLog.map((log) => (
                 <div key={log.id} className="flex items-start gap-4 p-4 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
                   <div className="shrink-0 pt-0.5">
                     <div className="w-2 h-2 rounded-full bg-[var(--color-accent-purple)] shadow-[0_0_8px_rgba(139,92,246,0.5)]" />
                   </div>
                   <div className="flex-1">
                     <div className="flex justify-between items-start mb-1">
                       <span className="text-sm font-bold text-gray-200">{log.event_type}</span>
                       <span className="text-[10px] text-gray-500">{new Date(log.created_at).toLocaleString()}</span>
                     </div>
                     <pre className="text-[10px] text-gray-400 font-mono bg-black/30 p-2 rounded mt-2 overflow-x-auto">
                       {JSON.stringify(log.details, null, 2)}
                     </pre>
                   </div>
                 </div>
               ))
             )}
           </div>
        </div>

      </div>
    </div>
  );
}
