import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../lib/api';
import {
  Key, Plus, Trash2, Copy, Check, Shield, Zap, Radio, Webhook,
  Code2, Server, Phone, Eye, EyeOff, Clock, CheckCircle2, XCircle, BookOpen
} from 'lucide-react';

interface ApiKey {
  id: string;
  prefix: string;
  is_active: boolean;
  created_at: string;
}

/* ─── Feature card definitions ─── */
const API_CAPABILITIES = [
  {
    icon: Radio,
    title: 'Real-Time Audio Streaming',
    description: 'Pipe 16kHz PCM audio from your telephony infrastructure via WebSocket. Get continuous ensemble risk scoring with sub-200ms latency.',
    endpoint: 'ws://host/ws/stream',
    color: 'var(--color-accent-primary)',
    bgColor: 'rgba(0,229,200,0.08)',
    borderColor: 'rgba(0,229,200,0.2)',
  },
  {
    icon: Shield,
    title: 'Deepfake Detection API',
    description: 'Upload audio files for offline forensic analysis using AASIST + XLS-R ensemble. Returns deepfake probability, spectral anomalies, and confidence intervals.',
    endpoint: 'POST /api/v1/analyze',
    color: '#a78bfa',
    bgColor: 'rgba(167,139,250,0.08)',
    borderColor: 'rgba(167,139,250,0.2)',
  },
  {
    icon: Zap,
    title: 'Automated Workflows',
    description: 'Trigger transaction holds, escalation flows, and compliance actions programmatically when risk thresholds are breached during live calls.',
    endpoint: 'POST /api/v1/alerts/workflows/execute',
    color: '#f97316',
    bgColor: 'rgba(249,115,22,0.08)',
    borderColor: 'rgba(249,115,22,0.2)',
  },
  {
    icon: Webhook,
    title: 'Webhook Events',
    description: 'Receive real-time HTTP POST notifications to your endpoint whenever a deepfake alert, identity drift, or high-risk transaction is detected.',
    endpoint: 'POST /api/v1/webhooks/configure',
    color: '#ec4899',
    bgColor: 'rgba(236,72,153,0.08)',
    borderColor: 'rgba(236,72,153,0.2)',
  },
];

const CODE_TABS = [
  {
    id: 'python',
    label: 'Python SDK',
    icon: Code2,
    color: '#10b981',
    badge: '16kHz PCM · Biometric Ensemble',
    code: `from voiceguard import VoiceGuardClient

client = VoiceGuardClient(api_key="vg_live_9f8a3b...")

# Connect to real-time telephony stream with contextual transaction metadata
stream = client.create_stream(
    caller_phone="+91-9820012345",
    location="Mumbai, MH (IN)",
    transaction_amount=50000.0,
    transfer_type="High-Value Wire Transfer"
)

# Pipe 16kHz mono audio frames
stream.send_pcm(audio_chunk_16k)

# Receive continuous ensemble risk scores
risk = stream.get_latest_risk()
print(f"Deepfake Risk: {risk.score * 100:.1f}%, Action: {risk.action_recommendation}")`,
  },
  {
    id: 'curl',
    label: 'cURL',
    icon: Server,
    color: '#06b6d4',
    badge: 'POST /api/v1/alerts/workflows/execute',
    code: `curl -X POST "http://localhost:8000/api/v1/alerts/workflows/execute" \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "action": "AUTO_HOLD_TRANSACTION",
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "caller_id": "+91 98200 12345",
    "amount": 50000.0,
    "reason": "AI voice synthesis artifacts detected on active wire transfer"
  }'`,
  },
  {
    id: 'websocket',
    label: 'WebSocket',
    icon: Radio,
    color: '#a78bfa',
    badge: 'ws://localhost:8000/ws/stream',
    code: `// Connect with caller context
const ws = new WebSocket("ws://localhost:8000/ws/stream?location=Mumbai&amount=50000&caller_phone=+919820012345");

// Send dynamic context updates during call
ws.send(JSON.stringify({
  type: "update_metadata",
  amount: 75000,
  transfer_type: "Crypto Withdrawal"
}));`,
  },
  {
    id: 'asterisk',
    label: 'Asterisk PBX',
    icon: Phone,
    color: '#f59e0b',
    badge: 'PJSIP Media Forking · ARI :8088',
    code: `[voiceguard-inbound]
; Route incoming SIP call from customer or bank agent to VoiceGuardAI
exten => _X.,1,NoOp(==> Inbound Call from: \${CALLERID(num)})
 same => n,Answer()
 same => n,Wait(0.2)
 same => n,Stasis(voiceguard_app,\${CALLERID(num)},\${EXTEN})
 same => n,Hangup()`,
  },
];

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [activeCodeTab, setActiveCodeTab] = useState('python');
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchKeys();
  }, []);

  const fetchKeys = async () => {
    try {
      const data = await apiFetch('/org/keys');
      setKeys(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    try {
      const data = await apiFetch('/org/keys', { method: 'POST' });
      setNewKey(data.key);
      setKeys([data, ...keys]);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRevokeKey = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this key? This action cannot be undone.')) return;
    try {
      await apiFetch(`/org/keys/${id}`, { method: 'DELETE' });
      setKeys(keys.map(k => k.id === id ? { ...k, is_active: false } : k));
    } catch (err) {
      console.error(err);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleKeyVisibility = (id: string) => {
    setVisibleKeys(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const activeTab = CODE_TABS.find(t => t.id === activeCodeTab) || CODE_TABS[0];

  return (
    <div className="min-h-screen pt-10 pb-12 px-4 sm:px-6 lg:px-8 max-w-[1440px] mx-auto">

      {/* ────── Page Header ────── */}
      <div className="mb-10">
        <h1 className="text-2xl font-bold text-[var(--color-sentinel-text)] flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--color-accent-primary)] to-[var(--color-accent-purple)] flex items-center justify-center shadow-lg" style={{ boxShadow: '0 4px 20px rgba(0,229,200,0.15)' }}>
            <Key className="w-5 h-5 text-white" />
          </div>
          API Keys & Integration
        </h1>
        <p className="text-sm text-[var(--color-sentinel-text-muted)] mt-1.5 pt-3">
          Manage authentication keys for your organisation's B2B integrations. Each key grants access to real-time audio analysis, automated workflows, and webhook event subscriptions.
        </p>
      </div>

      {/* ────── 1. What Your API Key Unlocks Section (First) ────── */}
      <div className="mb-10">
        <h2 className="text-base font-bold text-[var(--color-sentinel-text)] flex items-center gap-2 pb-4">
          <BookOpen className="w-4 h-4 text-[var(--color-accent-purple)]" />
          What Your API Key Unlocks
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {API_CAPABILITIES.map((cap, idx) => {
            const Icon = cap.icon;
            return (
              <motion.div
                key={cap.title}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="rounded-2xl border p-4 transition-all hover:border-opacity-60 flex flex-col justify-between group"
                style={{ borderColor: cap.borderColor, background: cap.bgColor }}
              >
                <div className="flex-1 flex items-center gap-3 mb-3">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 self-start" style={{ background: `${cap.color}15` }}>
                    <Icon className="w-[18px] h-[18px]" style={{ color: cap.color }} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h4 className="text-[0.8125rem] font-bold text-[var(--color-sentinel-text)] pb-2">{cap.title}</h4>
                    <p className="text-[11px] text-[var(--color-sentinel-text-muted)] leading-relaxed">{cap.description}</p>
                  </div>
                </div>
                <div className="pt-2 border-t border-white/5">
                  <code className="text-[10px] font-mono px-2 py-1 rounded-md bg-[#0f111a] border border-[var(--color-sentinel-border)] inline-block truncate max-w-full" style={{ color: cap.color }}>
                    {cap.endpoint}
                  </code>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* ────── 2. API Keys Section (Below Unlocks Section) ────── */}
      <div className="mb-10 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-[var(--color-sentinel-border)]">
          <div>
            <h2 className="text-base font-bold text-[var(--color-sentinel-text)] flex items-center gap-2">
              <Key className="w-4 h-4 text-[var(--color-accent-primary)]" />
              Active API Keys
            </h2>
            <span className="text-xs text-[var(--color-sentinel-text-dim)] font-mono mt-0.5 block">
              {keys.filter(k => k.is_active).length} active · {keys.filter(k => !k.is_active).length} revoked
            </span>
          </div>
          <button
            onClick={handleCreateKey}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] font-semibold hover:brightness-110 active:scale-95 transition-all shadow-lg"
            style={{ boxShadow: '0 6px 24px rgba(0,229,200,0.2)' }}
          >
            <Plus className="w-4 h-4" />
            Generate New Key
          </button>
        </div>

        {/* New Key Alert */}
        <AnimatePresence>
          {newKey && (
            <motion.div
              initial={{ opacity: 0, y: -12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="p-5 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 backdrop-blur-sm"
            >
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-bold text-emerald-400">API Key Generated Successfully</h3>
              </div>
              <p className="text-xs text-[var(--color-sentinel-text-muted)] mb-3">
                Copy this key now — it will <strong className="text-[var(--color-sentinel-text)]">never be shown again</strong>. Store it securely in your environment variables or secrets manager.
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-[#0f111a] px-4 py-3 rounded-xl font-mono text-sm text-emerald-300 border border-emerald-500/10 break-all">
                  {newKey}
                </code>
                <button
                  onClick={() => copyToClipboard(newKey)}
                  className="shrink-0 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 transition-all"
                >
                  {copied ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Key List */}
        {loading ? (
          <div className="flex items-center justify-center py-16 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)]">
            <div className="w-8 h-8 border-3 border-[var(--color-accent-primary)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : keys.length === 0 ? (
          <div className="text-center py-16 rounded-2xl border border-dashed border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)]">
            <Key className="w-10 h-10 text-[var(--color-sentinel-text-dim)] mx-auto mb-3" />
            <h3 className="text-sm font-bold text-[var(--color-sentinel-text)] mb-1">No API Keys Yet</h3>
            <p className="text-xs text-[var(--color-sentinel-text-muted)]">Generate your first key to get started with the API.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {keys.map((key, idx) => (
              <motion.div
                key={key.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className={`rounded-2xl border p-4 transition-all ${
                  key.is_active
                    ? 'border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] hover:border-[var(--color-sentinel-text-dim)]'
                    : 'border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] opacity-50'
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                      key.is_active ? 'bg-[rgba(0,229,200,0.1)]' : 'bg-[rgba(239,68,68,0.1)]'
                    }`}>
                      <Key className={`w-4 h-4 ${key.is_active ? 'text-[var(--color-accent-primary)]' : 'text-red-400'}`} />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <code className="text-sm font-mono text-[var(--color-sentinel-text)] font-semibold truncate">
                          {visibleKeys.has(key.id) ? key.prefix + '••••••••••••' : key.prefix + '••••'}
                        </code>
                        <button
                          onClick={() => toggleKeyVisibility(key.id)}
                          className="p-1 rounded-md text-[var(--color-sentinel-text-dim)] hover:text-[var(--color-sentinel-text)] transition-colors"
                        >
                          {visibleKeys.has(key.id) ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          key.is_active
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}>
                          {key.is_active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                          {key.is_active ? 'ACTIVE' : 'REVOKED'}
                        </span>
                        <span className="text-[11px] text-[var(--color-sentinel-text-dim)] flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(key.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </span>
                      </div>
                    </div>
                  </div>

                  {key.is_active && (
                    <button
                      onClick={() => handleRevokeKey(key.id)}
                      className="shrink-0 inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-red-500/20 text-red-400 text-xs font-semibold hover:bg-red-500/10 hover:border-red-500/40 transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Revoke
                    </button>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

        {/* ────── Developer Integration Section ────── */}
        <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] overflow-hidden">
          {/* Header */}
          <div className="px-6 py-5 border-b border-[var(--color-sentinel-border)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-[var(--color-sentinel-text)] flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400"><Code2 className="w-4 h-4" /></span>
                Developer Integration Guide
              </h2>
              <p className="text-xs text-[var(--color-sentinel-text-muted)] mt-1 pt-2">
                Connect VoiceGuardAI into core banking, contact centre platforms, and VoIP PBX setups using these code examples.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={async () => {
                  try {
                    const res = await apiFetch('/webhooks/test', { method: 'POST' });
                    alert(`Webhook Test Dispatched! (Alert ID: ${res.dispatch_result?.payload?.alert_id})`);
                  } catch (e) {
                    alert(`Webhook Test Failed: ${e}`);
                  }
                }}
                className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl transition shadow-lg flex items-center gap-1.5"
              >
                🚀 Test Webhook
              </button>
              <button
                onClick={async () => {
                  try {
                    const res = await apiFetch('/alerts/workflows/execute', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        action: 'AUTO_HOLD_TRANSACTION',
                        reason: 'B2B Integration Playground verification trigger',
                      }),
                    });
                    alert(`Workflow Executed!\nAction: ${res.action}\nWorkflow ID: ${res.workflow_id}\nDescription: ${res.description}`);
                  } catch (e) {
                    alert(`Workflow Test Failed: ${e}`);
                  }
                }}
                className="px-3.5 py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-xl transition shadow-lg flex items-center gap-1.5"
              >
                🔒 Test Hold Workflow
              </button>
            </div>
          </div>

          {/* Tab Bar */}
          <div className="px-6 pt-4 flex items-center gap-1 overflow-x-auto border-b border-[var(--color-sentinel-border)]">
            {CODE_TABS.map((tab) => {
              const TabIcon = tab.icon;
              const isActive = activeCodeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveCodeTab(tab.id)}
                  className={`relative flex items-center gap-2 px-4 py-2.5 text-xs font-bold rounded-t-xl transition-all ${
                    isActive
                      ? 'text-[var(--color-sentinel-text)] bg-[#0f111a]'
                      : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
                  }`}
                >
                  <TabIcon className="w-3.5 h-3.5" style={{ color: isActive ? tab.color : undefined }} />
                  {tab.label}
                  {isActive && (
                    <motion.div
                      layoutId="code-tab-indicator"
                      className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
                      style={{ background: tab.color }}
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* Code Block */}
          <div className="p-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-mono text-[var(--color-sentinel-text-dim)]">{activeTab.badge}</span>
              <button
                onClick={() => copyToClipboard(activeTab.code)}
                className="flex items-center gap-1.5 text-[10px] font-bold text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] transition-colors"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <pre className="bg-[#0f111a] p-5 rounded-xl text-xs font-mono overflow-x-auto leading-relaxed border border-[#1e2030]" style={{ color: activeTab.color }}>
              {activeTab.code}
            </pre>
          </div>
        </div>
    </div>
  );
}
