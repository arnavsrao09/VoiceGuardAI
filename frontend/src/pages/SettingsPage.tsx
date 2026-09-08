import { useState } from 'react';
import { Settings, Sliders, Cpu, Save, RefreshCw, Bell, Mail, MessageSquare, Webhook, Shield, Download, ToggleLeft, ToggleRight } from 'lucide-react';
import { apiFetch } from '../lib/api';

export default function SettingsPage() {
  const [vadThreshold, setVadThreshold] = useState(0.5);
  const [deepfakeThreshold, setDeepfakeThreshold] = useState(0.6);
  const [speakerThreshold, setSpeakerThreshold] = useState(0.75);

  const [wDeepfake, setWDeepfake] = useState(0.40);
  const [wSpeaker, setWSpeaker] = useState(0.25);
  const [wProsody, setWProsody] = useState(0.15);
  const [wDrift, setWDrift] = useState(0.10);

  // Privacy Mode Toggle
  const [privacyMode, setPrivacyMode] = useState(true); // Default: Edge/RAM mode ON
  const [privacyToggling, setPrivacyToggling] = useState(false);

  // Notification Settings (UI display — actual config is in backend .env)
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [smsEnabled, setSmsEnabled] = useState(false);
  const [webhookEnabled, setWebhookEnabled] = useState(true);

  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const togglePrivacyMode = async () => {
    setPrivacyToggling(true);
    try {
      const newMode = !privacyMode;
      await apiFetch(`/privacy/mode?enabled=${newMode}`, { method: 'POST' });
      setPrivacyMode(newMode);
    } catch (err) {
      console.error('Failed to toggle privacy mode:', err);
    } finally {
      setPrivacyToggling(false);
    }
  };

  const handleExportCompliance = async () => {
    try {
      const data = await apiFetch('/privacy/compliance-report');
      const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute("href", jsonStr);
      downloadAnchor.setAttribute("download", `VoiceGuardAI_DPDP_GDPR_Compliance_Report_${Date.now()}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    } catch (err) {
      console.error('Failed to export compliance report:', err);
    }
  };

  return (
    <div className="min-h-screen pt-24 pb-12 px-4 sm:px-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-sentinel-text)] flex items-center gap-2.5">
              <Settings className="w-6 h-6 text-[var(--color-accent-primary)]" />
              System Thresholds & Model Settings
            </h1>
            <p className="text-sm text-[var(--color-sentinel-text-muted)] mt-1">
              Configure detection thresholds and ensemble fusion weights for live inference.
            </p>
          </div>

          <button
            onClick={handleSave}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] font-semibold hover:brightness-110 active:scale-95 transition-all shadow-lg"
            style={{ boxShadow: '0 6px 24px rgba(0,229,200,0.2)' }}
          >
            {saved ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saved ? 'Saved!' : 'Save Settings'}
          </button>
        </div>

        {/* Detection Thresholds */}
        <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6 mb-6">
          <h2 className="text-base font-bold text-[var(--color-sentinel-text)] mb-4 flex items-center gap-2">
            <Sliders className="w-5 h-5 text-[var(--color-accent-primary)]" />
            Detection Sensitivity Thresholds
          </h2>

          <div className="flex flex-col gap-6">
            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-[var(--color-sentinel-text)]">Silero VAD Speech Probability Threshold</span>
                <span className="text-[var(--color-accent-primary)]">{vadThreshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={vadThreshold}
                onChange={(e) => setVadThreshold(parseFloat(e.target.value))}
                className="w-full accent-[var(--color-accent-primary)] cursor-pointer"
              />
              <p className="text-[10px] text-[var(--color-sentinel-text-dim)] mt-1">Frames with speech probability above this are sent to the ML pipeline.</p>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-[var(--color-sentinel-text)]">Deepfake Detection Alert Threshold</span>
                <span className="text-[var(--color-accent-primary)]">{deepfakeThreshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.3"
                max="0.95"
                step="0.05"
                value={deepfakeThreshold}
                onChange={(e) => setDeepfakeThreshold(parseFloat(e.target.value))}
                className="w-full accent-[var(--color-accent-primary)] cursor-pointer"
              />
              <p className="text-[10px] text-[var(--color-sentinel-text-dim)] mt-1">Triggers HIGH / CRITICAL alerts when AASIST + XLS-R probability exceeds this.</p>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-[var(--color-sentinel-text)]">Speaker Verification Cosine Match Threshold</span>
                <span className="text-[var(--color-accent-primary)]">{speakerThreshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="0.9"
                step="0.05"
                value={speakerThreshold}
                onChange={(e) => setSpeakerThreshold(parseFloat(e.target.value))}
                className="w-full accent-[var(--color-accent-primary)] cursor-pointer"
              />
              <p className="text-[10px] text-[var(--color-sentinel-text-dim)] mt-1">Minimum ECAPA-TDNN embedding similarity required to verify enrolled speaker identity.</p>
            </div>
          </div>
        </div>

        {/* Model Ensemble Weights */}
        <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6">
          <h2 className="text-base font-bold text-[var(--color-sentinel-text)] mb-4 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-[var(--color-accent-purple)]" />
            Ensemble Fusion Weights (Sum = 1.00)
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="text-xs font-semibold text-[var(--color-sentinel-text-muted)] mb-1 block">AASIST + XLS-R Deepfake Weight ({wDeepfake.toFixed(2)})</label>
              <input
                type="range"
                min="0.1"
                max="0.7"
                step="0.05"
                value={wDeepfake}
                onChange={(e) => setWDeepfake(parseFloat(e.target.value))}
                className="w-full accent-[var(--color-accent-purple)] cursor-pointer"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--color-sentinel-text-muted)] mb-1 block">ECAPA-TDNN Speaker Weight ({wSpeaker.toFixed(2)})</label>
              <input
                type="range"
                min="0.1"
                max="0.5"
                step="0.05"
                value={wSpeaker}
                onChange={(e) => setWSpeaker(parseFloat(e.target.value))}
                className="w-full accent-[var(--color-accent-purple)] cursor-pointer"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--color-sentinel-text-muted)] mb-1 block">Prosody Forensics Weight ({wProsody.toFixed(2)})</label>
              <input
                type="range"
                min="0.05"
                max="0.4"
                step="0.05"
                value={wProsody}
                onChange={(e) => setWProsody(parseFloat(e.target.value))}
                className="w-full accent-[var(--color-accent-purple)] cursor-pointer"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--color-sentinel-text-muted)] mb-1 block">Speaker Drift Anomaly Weight ({wDrift.toFixed(2)})</label>
              <input
                type="range"
                min="0.05"
                max="0.3"
                step="0.05"
                value={wDrift}
                onChange={(e) => setWDrift(parseFloat(e.target.value))}
                className="w-full accent-[var(--color-accent-purple)] cursor-pointer"
              />
            </div>
          </div>
        </div>
        {/* Notification & Dispatch Settings */}
        <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6 mt-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-[var(--color-sentinel-text)] flex items-center gap-2">
                <Bell className="w-5 h-5 text-amber-400" />
                Multi-Channel Alert Dispatch
              </h2>
              <p className="text-xs text-[var(--color-sentinel-text-muted)] mt-1">
                Configure how and where high-risk alerts are delivered.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={`p-4 rounded-xl border transition-all cursor-pointer ${emailEnabled ? 'bg-indigo-500/10 border-indigo-500/30' : 'bg-[var(--color-sentinel-surface-2)] border-[var(--color-sentinel-border)]'}`} onClick={() => setEmailEnabled(!emailEnabled)}>
              <div className="flex justify-between items-start mb-2">
                <div className={`p-2 rounded-lg ${emailEnabled ? 'bg-indigo-500/20 text-indigo-400' : 'bg-gray-800 text-gray-500'}`}>
                  <Mail className="w-4 h-4" />
                </div>
                {emailEnabled ? <ToggleRight className="w-5 h-5 text-indigo-400" /> : <ToggleLeft className="w-5 h-5 text-gray-500" />}
              </div>
              <h4 className="text-xs font-bold text-gray-200">Email Alerts</h4>
              <p className="text-[10px] text-gray-500 mt-1">SMTP HTML Reports</p>
            </div>

            <div className={`p-4 rounded-xl border transition-all cursor-pointer ${smsEnabled ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-[var(--color-sentinel-surface-2)] border-[var(--color-sentinel-border)]'}`} onClick={() => setSmsEnabled(!smsEnabled)}>
              <div className="flex justify-between items-start mb-2">
                <div className={`p-2 rounded-lg ${smsEnabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-800 text-gray-500'}`}>
                  <MessageSquare className="w-4 h-4" />
                </div>
                {smsEnabled ? <ToggleRight className="w-5 h-5 text-emerald-400" /> : <ToggleLeft className="w-5 h-5 text-gray-500" />}
              </div>
              <h4 className="text-xs font-bold text-gray-200">SMS / Twilio</h4>
              <p className="text-[10px] text-gray-500 mt-1">Instant Text Notifications</p>
            </div>

            <div className={`p-4 rounded-xl border transition-all cursor-pointer ${webhookEnabled ? 'bg-purple-500/10 border-purple-500/30' : 'bg-[var(--color-sentinel-surface-2)] border-[var(--color-sentinel-border)]'}`} onClick={() => setWebhookEnabled(!webhookEnabled)}>
              <div className="flex justify-between items-start mb-2">
                <div className={`p-2 rounded-lg ${webhookEnabled ? 'bg-purple-500/20 text-purple-400' : 'bg-gray-800 text-gray-500'}`}>
                  <Webhook className="w-4 h-4" />
                </div>
                {webhookEnabled ? <ToggleRight className="w-5 h-5 text-purple-400" /> : <ToggleLeft className="w-5 h-5 text-gray-500" />}
              </div>
              <h4 className="text-xs font-bold text-gray-200">Enterprise Webhook</h4>
              <p className="text-[10px] text-gray-500 mt-1">JSON HTTP POST Payloads</p>
            </div>
          </div>
        </div>

        {/* Privacy & Compliance Module */}
        <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6 mt-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-[var(--color-sentinel-text)] flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                  <Shield className="w-5 h-5" />
                </div>
                Privacy & Data Protection Compliance (DPDP Act 2023 / GDPR)
              </h2>
              <p className="text-xs text-[var(--color-sentinel-text-muted)] mt-1">
                Configure data minimization rules and edge inference settings.
              </p>
            </div>
            {privacyMode && (
              <span className="px-3 py-1 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                ZERO RETENTION ACTIVE
              </span>
            )}
          </div>

          <div className="space-y-4">
            <div className={`flex items-center justify-between p-4 rounded-xl border transition-all ${privacyMode ? 'bg-emerald-500/5 border-emerald-500/30' : 'bg-[var(--color-sentinel-surface-2)] border-[var(--color-sentinel-border-subtle)]'}`}>
              <div className="flex-1 pr-6">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-[var(--color-sentinel-text)]">Edge / RAM-Only Processing Mode</h4>
                  <span className={`text-[10px] px-2 py-0.5 rounded uppercase font-bold ${privacyMode ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-800 text-gray-400'}`}>
                    {privacyMode ? 'ENFORCED' : 'DISABLED'}
                  </span>
                </div>
                <p className="text-[11px] text-[var(--color-sentinel-text-dim)] mt-1.5 leading-relaxed">
                  Processes PCM audio transiently in RAM. Audio buffers are purged immediately after feature extraction. 
                  Zero raw audio recordings are written to disk when this is active.
                </p>
              </div>
              
              <button
                onClick={togglePrivacyMode}
                disabled={privacyToggling}
                className="shrink-0"
              >
                {privacyMode ? (
                  <ToggleRight className={`w-10 h-10 text-emerald-400 ${privacyToggling ? 'opacity-50' : 'hover:brightness-110'} transition-all`} />
                ) : (
                  <ToggleLeft className={`w-10 h-10 text-gray-500 ${privacyToggling ? 'opacity-50' : 'hover:text-gray-400'} transition-all`} />
                )}
              </button>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
              <div>
                <h4 className="text-sm font-bold text-[var(--color-sentinel-text)]">Regulatory Compliance Report</h4>
                <p className="text-[11px] text-[var(--color-sentinel-text-dim)] mt-0.5">
                  Generate audit documentation for Digital Personal Data Protection (DPDP) Act 2023 & GDPR Article 9.
                </p>
              </div>
              <button
                onClick={handleExportCompliance}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--color-sentinel-surface-3)] border border-[var(--color-sentinel-border)] text-gray-300 text-xs font-bold hover:bg-gray-800 transition shadow-sm"
              >
                <Download className="w-3.5 h-3.5" />
                Export Audit JSON
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
