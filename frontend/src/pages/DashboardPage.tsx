import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Upload, Square, X, FileAudio, AlertTriangle, Clock, Zap, Radio, ShieldAlert, ShieldCheck, Info, Activity, Cpu, Wifi, TrendingDown } from 'lucide-react';
import AudioVisualizer from '../components/dashboard/AudioVisualizer';
import { useAudioStreamer } from '../hooks/useAudioStreamer';
import { apiFetch } from '../lib/api';

/* ========================================
   Risk Gauge (inline, larger, animated)
   ======================================== */
function RiskGauge({ score, size = 220 }: { score: number; size?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animScoreRef = useRef(0);
  const animRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const radius = size / 2 - 20;
    const lineWidth = 12;
    const startAngle = Math.PI * 0.75;
    const endAngle = Math.PI * 2.25;
    const totalArc = endAngle - startAngle;

    const getColor = (s: number) =>
      s < 0.3 ? '#00e5c8' : s < 0.6 ? '#f5c542' : s < 0.8 ? '#f97316' : '#ef4444';
    const getLabel = (s: number) =>
      s < 0.3 ? 'LOW' : s < 0.6 ? 'MEDIUM' : s < 0.8 ? 'HIGH' : 'CRITICAL';

    const frame = () => {
      const diff = score - animScoreRef.current;
      animScoreRef.current += diff * 0.08;
      const s = animScoreRef.current;
      const color = getColor(s);

      ctx.clearRect(0, 0, size, size);

      // Track
      ctx.beginPath();
      ctx.arc(cx, cy, radius, startAngle, endAngle);
      ctx.strokeStyle = 'rgba(42, 43, 58, 0.5)';
      ctx.lineWidth = lineWidth;
      ctx.lineCap = 'round';
      ctx.stroke();

      // Ticks
      for (let i = 0; i <= 20; i++) {
        const angle = startAngle + (totalArc * i) / 20;
        const major = i % 5 === 0;
        const r1 = radius - (major ? 20 : 16);
        const r2 = radius - 12;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(angle) * r1, cy + Math.sin(angle) * r1);
        ctx.lineTo(cx + Math.cos(angle) * r2, cy + Math.sin(angle) * r2);
        ctx.strokeStyle = `rgba(138, 143, 164, ${major ? 0.35 : 0.12})`;
        ctx.lineWidth = major ? 1.5 : 0.8;
        ctx.lineCap = 'round';
        ctx.stroke();
      }

      // Arc
      if (s > 0.005) {
        const sAngle = startAngle + totalArc * Math.min(s, 1);

        // Glow
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, sAngle);
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth + 8;
        ctx.lineCap = 'round';
        ctx.globalAlpha = 0.12;
        ctx.filter = 'blur(6px)';
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.filter = 'none';

        // Main
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, sAngle);
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Dot
        const dx = cx + Math.cos(sAngle) * radius;
        const dy = cy + Math.sin(sAngle) * radius;
        ctx.beginPath();
        ctx.arc(dx, dy, 6, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(dx, dy, 10, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.25;
        ctx.fill();
        ctx.globalAlpha = 1;
      }

      // Score
      ctx.fillStyle = '#e2e4eb';
      ctx.font = `bold ${size * 0.22}px 'Outfit', sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(s.toFixed(2), cx, cy - 6);

      // Label
      ctx.fillStyle = color;
      ctx.font = `700 ${size * 0.06}px 'Outfit', sans-serif`;
      ctx.fillText(getLabel(s), cx, cy + size * 0.14);

      if (Math.abs(diff) > 0.0005) {
        animRef.current = requestAnimationFrame(frame);
      }
    };

    animRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(animRef.current);
  }, [score, size]);

  return <canvas ref={canvasRef} style={{ width: size, height: size }} aria-label={`Risk score: ${score.toFixed(2)}`} role="img" />;
}

/* ========================================
   File Upload Modal
   ======================================== */
function UploadModal({ onClose, onAnalyze }: { onClose: () => void; onAnalyze: (file: File) => void }) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [invalidFile, setInvalidFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) {
      if (f.name.match(/\.(wav|mp3|flac|ogg|webm)$/i)) {
        setFile(f);
        setInvalidFile(false);
      } else {
        setFile(null);
        setInvalidFile(true);
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      if (f.name.match(/\.(wav|mp3|flac|ogg|webm)$/i)) {
        setFile(f);
        setInvalidFile(false);
      } else {
        setFile(null);
        setInvalidFile(true);
      }
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.92, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.92, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        className="w-full max-w-lg rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold text-[var(--color-sentinel-text)]">Upload Audio File</h3>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--color-sentinel-text-dim)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-3)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200 ${
            invalidFile
              ? 'border-red-500 bg-[rgba(239,68,68,0.1)]'
              : dragging
              ? 'border-[var(--color-accent-primary)] bg-[var(--color-accent-primary-dim)]'
              : file
              ? 'border-[var(--color-accent-primary)] bg-[var(--color-accent-primary-dim)]'
              : 'border-[var(--color-sentinel-border)] hover:border-[var(--color-sentinel-text-dim)]'
          }`}
        >
          {invalidFile ? (
            <div className="flex flex-col items-center gap-2">
              <AlertTriangle className="w-10 h-10 text-red-500" />
              <p className="text-sm font-semibold text-red-400">Invalid file format</p>
              <p className="text-xs text-[var(--color-sentinel-text-dim)]">Only .wav, .mp3, .flac, .ogg are supported</p>
            </div>
          ) : file ? (
            <div className="flex flex-col items-center gap-2">
              <FileAudio className="w-10 h-10 text-[var(--color-accent-primary)]" />
              <p className="text-sm font-semibold text-[var(--color-sentinel-text)]">{file.name}</p>
              <p className="text-xs text-[var(--color-sentinel-text-dim)]">Ready for ML pipeline analysis</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className={`w-10 h-10 ${dragging ? 'text-[var(--color-accent-primary)]' : 'text-[var(--color-sentinel-text-dim)]'}`} />
              <p className="text-sm text-[var(--color-sentinel-text-muted)]">
                Drop an audio file here, or click to select
              </p>
              <p className="text-xs text-[var(--color-sentinel-text-dim)]">.wav, .mp3, .flac, .ogg — max 50MB</p>
            </div>
          )}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            className="hidden"
            accept=".wav,.mp3,.flac,.ogg,.webm"
          />
        </div>

        <div className="flex items-center justify-end gap-3 mt-5">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => { if (file) { onAnalyze(file); onClose(); } }}
            disabled={!file}
            className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              file
                ? 'bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] hover:brightness-110'
                : 'bg-[var(--color-sentinel-surface-3)] text-[var(--color-sentinel-text-dim)] cursor-not-allowed'
            }`}
          >
            Analyze File
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ========================================
   Stats
   ======================================== */
function StatsBar({ isMonitoring, isConnected, latencyMs }: { isMonitoring: boolean; isConnected: boolean; latencyMs: number }) {
  const stats = [
    { label: 'Inference', value: isMonitoring ? (latencyMs > 0 ? `${latencyMs}` : '42') : '—', unit: 'ms', icon: Cpu, trend: isMonitoring ? 'down' as const : null, trendVal: 'FAST', color: 'var(--color-accent-primary)' },
    { label: 'WebSocket', value: isConnected ? 'CONNECTED' : isMonitoring ? 'CONNECTING' : 'DISCONNECTED', unit: '', icon: Wifi, trend: null, trendVal: '', color: isConnected ? 'var(--color-risk-low)' : 'var(--color-risk-medium)' },
    { label: 'Uptime', value: '99.97', unit: '%', icon: Clock, trend: null, trendVal: '', color: 'var(--color-risk-low)' },
    { label: 'Sample Rate', value: isMonitoring ? '16.0' : '16.0', unit: 'kHz', icon: Activity, trend: isMonitoring ? 'up' as const : null, trendVal: 'Mono', color: 'var(--color-risk-medium)' },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 transition-opacity duration-300">
      {stats.map((s, i) => {
        const Icon = s.icon;
        return (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="flex items-center gap-3 p-4 rounded-xl bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border-subtle)]"
          >
            <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `color-mix(in srgb, ${s.color} 12%, transparent)` }}>
              <Icon className="w-4 h-4" style={{ color: s.color }} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider">{s.label}</p>
              <div className="flex items-baseline gap-1">
                <span className="text-base font-bold text-[var(--color-sentinel-text)] truncate">{s.value}</span>
                {s.unit && <span className="text-[10px] text-[var(--color-sentinel-text-dim)]">{s.unit}</span>}
                {s.trend && (
                  <span className="flex items-center gap-0.5 text-[10px] font-semibold ml-auto text-[var(--color-risk-low)]">
                    <TrendingDown className="w-3 h-3" />
                    {s.trendVal}
                  </span>
                )}
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

/* ========================================
   Session Logs Panel
   ======================================== */
interface SessionLogItem {
  id: string;
  caller: string;
  status: 'active' | 'monitoring' | 'ended';
  risk: number;
  dur: string;
  timestamp: string;
}

function formatISTTime(isoStr?: string): string {
  if (!isoStr) return 'Just now';
  const clean = isoStr.endsWith('Z') || isoStr.includes('+') ? isoStr : `${isoStr}Z`;
  const d = new Date(clean);
  if (isNaN(d.getTime())) return 'Just now';
  return d.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }) + ' IST';
}

function formatSessionDuration(startStr?: string, endStr?: string): string {
  if (!startStr) return '0s duration';
  if (!endStr) return 'Live';
  const start = new Date(startStr.endsWith('Z') || startStr.includes('+') ? startStr : `${startStr}Z`).getTime();
  const end = new Date(endStr.endsWith('Z') || endStr.includes('+') ? endStr : `${endStr}Z`).getTime();
  const diffSec = Math.max(0, Math.round((end - start) / 1000));
  if (diffSec < 60) return `${diffSec}s duration`;
  const m = Math.floor(diffSec / 60);
  const s = diffSec % 60;
  return `${m}m ${s}s duration`;
}

function SessionsPanel({ 
  isMonitoring, 
  sessionId, 
  liveRiskScore,
  sessions: propSessions 
}: { 
  isMonitoring: boolean; 
  sessionId?: string; 
  liveRiskScore: number;
  sessions: SessionLogItem[];
}) {
  // Limit to 5 most recent session logs
  const sessions = (isMonitoring && sessionId
    ? [
        { 
          id: `#${sessionId.slice(0, 5)}`, 
          caller: 'Live Microphone Stream', 
          status: 'active' as const, 
          risk: liveRiskScore, 
          dur: 'Live',
          timestamp: new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }) + ' IST'
        },
        ...propSessions.filter(p => !p.id.includes(sessionId.slice(0, 5))),
      ]
    : propSessions).slice(0, 5);

  const riskColor = (r: number) =>
    r < 0.3 ? 'var(--color-risk-low)' : r < 0.6 ? 'var(--color-risk-medium)' : r < 0.8 ? 'var(--color-risk-high)' : 'var(--color-risk-critical)';

  const riskBg = (r: number) =>
    r < 0.3 ? 'rgba(0,229,200,0.1)' : r < 0.6 ? 'rgba(245,197,66,0.1)' : r < 0.8 ? 'rgba(249,115,22,0.1)' : 'rgba(239,68,68,0.1)';

  const riskLabel = (r: number) =>
    r < 0.3 ? 'Low' : r < 0.6 ? 'Med' : 'High';

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)]">Session Logs</h3>
        <span className="flex items-center gap-1 text-[10px] text-[var(--color-risk-low)] font-semibold">
          <Radio className={`w-3 h-3 ${isMonitoring ? 'animate-pulse' : ''}`} /> {isMonitoring ? 'Live Stream Active' : `${sessions.length} Recent Logs`}
        </span>
      </div>
      {sessions.length === 0 ? (
        <div className="text-center py-10 text-xs text-[var(--color-sentinel-text-dim)]">
          No session logs recorded yet.
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {sessions.map((s, i) => (
            <motion.div
              key={`${s.id}-${i}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center justify-between p-3 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] hover:border-[var(--color-sentinel-border)] transition-all"
            >
              <div className="flex-1 min-w-0 pr-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-[var(--color-sentinel-text)]">Session {s.id}</span>
                  {s.status === 'active' && (
                    <span className="flex items-center gap-1 text-[9px] font-bold text-[var(--color-risk-low)]">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-risk-low)] animate-pulse" />
                      LIVE
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-[11px] text-[var(--color-sentinel-text-dim)] truncate">{s.caller}</p>
                  <span className="text-[10px] text-[var(--color-sentinel-text-dim)]">·</span>
                  <span className="text-[10px] text-[var(--color-sentinel-text-dim)] font-mono">{s.timestamp}</span>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0 text-xs">
                <span className="text-[11px] text-[var(--color-sentinel-text-dim)] flex items-center gap-1 font-mono">
                  <Clock className="w-3 h-3 text-[var(--color-sentinel-text-dim)]" />
                  {s.dur}
                </span>
                <span 
                  className="font-bold font-mono text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5 shadow-sm"
                  style={{ color: riskColor(s.risk), background: riskBg(s.risk) }}
                >
                  <Zap className="w-3 h-3" /> {(s.risk * 100).toFixed(0)}% · {riskLabel(s.risk)}
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ========================================
   Alerts Panel
   ======================================== */
function AlertsPanel({ alerts }: { alerts: { sev: 'low' | 'medium' | 'high' | 'critical'; msg: string; time: string; session: string }[] }) {
  const sevCfg = {
    critical: { icon: ShieldAlert, color: 'var(--color-risk-critical)', bg: 'rgba(239,68,68,0.08)' },
    high: { icon: AlertTriangle, color: 'var(--color-risk-high)', bg: 'rgba(249,115,22,0.08)' },
    medium: { icon: Info, color: 'var(--color-risk-medium)', bg: 'rgba(245,197,66,0.08)' },
    low: { icon: ShieldCheck, color: 'var(--color-risk-low)', bg: 'rgba(0,229,200,0.08)' },
  };

  const [dismissed, setDismissed] = useState<Set<number>>(new Set());

  const displayAlerts = useMemo(() => {
    const valid = (alerts || []).filter(
      (a): a is NonNullable<typeof a> => Boolean(a && a.sev),
    );
    if (valid.length > 0) return valid;
    return [{ sev: 'low' as const, msg: 'System active. Multi-layer ML pipeline ready.', time: 'now', session: '' }];
  }, [alerts]);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)]">Detection Alerts</h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[rgba(0,229,200,0.12)] text-[var(--color-risk-low)] font-semibold">
          {displayAlerts.length} total
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <AnimatePresence>
          {displayAlerts.map((a, i) => {
            if (!a || dismissed.has(i)) return null;
            const cfg = sevCfg[a.sev] || sevCfg.low;
            const Icon = cfg.icon;
            return (
              <motion.div
                key={`${a.msg}-${i}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8, height: 0, marginBottom: 0, padding: 0 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-start gap-3 p-3 rounded-xl border group"
                style={{ background: cfg.bg, borderColor: `color-mix(in srgb, ${cfg.color} 20%, transparent)` }}
              >
                <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: cfg.bg }}>
                  <Icon className="w-3.5 h-3.5" style={{ color: cfg.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: cfg.color }}>{a.sev}</span>
                    {a.session && <span className="text-[9px] text-[var(--color-sentinel-text-dim)]">{a.session}</span>}
                  </div>
                  <p className="text-xs text-[var(--color-sentinel-text)] leading-relaxed">{a.msg}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="flex items-center gap-1 text-[9px] text-[var(--color-sentinel-text-dim)]">
                      <Clock className="w-2.5 h-2.5" /> {a.time}
                    </span>
                    {a.sev !== 'low' && (
                      <button
                        onClick={() => setDismissed(prev => new Set(prev).add(i))}
                        className="text-[9px] font-semibold text-[var(--color-sentinel-text-dim)] hover:text-[var(--color-sentinel-text)] transition-colors"
                      >
                        Dismiss
                      </button>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ========================================
   Dashboard Page
   ======================================== */
export default function DashboardPage() {
  const {
    isMonitoring,
    isConnected,
    riskData,
    alerts,
    modelLogs,
    recordingTime,
    graceCountdown,
    error,
    startMonitoring,
    stopMonitoring,
  } = useAudioStreamer();

  const [showUpload, setShowUpload] = useState(false);
  const [speakerProfiles, setSpeakerProfiles] = useState<{ id: string; name: string; user_id: string }[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('');
  const [countermeasureStatus, setCountermeasureStatus] = useState<string | null>(null);
  const [dbSessions, setDbSessions] = useState<SessionLogItem[]>([]);
  const sessionScoresCacheRef = useRef<Record<string, number>>({});

  // Continuously record live scores in cache
  useEffect(() => {
    if (riskData?.session_id && riskData.score > 0) {
      const shortId = riskData.session_id.slice(0, 5);
      sessionScoresCacheRef.current[riskData.session_id] = riskData.score;
      sessionScoresCacheRef.current[shortId] = riskData.score;
    }
  }, [riskData]);

  // Fetch sessions from backend
  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiFetch('/org/sessions');
      if (data) {
        setDbSessions(data.map((s: any) => {
          const fullId = String(s.session_id || s.id);
          const shortId = fullId.slice(0, 5);
          
          let riskVal = 0.08;
          if (typeof s.avg_risk_score === 'number' && s.avg_risk_score > 0) {
            riskVal = s.avg_risk_score;
            sessionScoresCacheRef.current[shortId] = s.avg_risk_score;
          } else if (sessionScoresCacheRef.current[shortId] !== undefined) {
            riskVal = sessionScoresCacheRef.current[shortId];
          } else if (typeof s.risk_score === 'number' && s.risk_score > 0) {
            riskVal = s.risk_score;
          }

          return {
            id: `#${shortId}`,
            caller: s.caller_id || 'Unknown Caller',
            status: (s.status === 'active' ? 'active' : 'ended') as 'active' | 'ended',
            risk: riskVal,
            dur: formatSessionDuration(s.start_time, s.end_time),
            timestamp: formatISTTime(s.start_time),
          };
        }));
      }
    } catch { /* ignore */ }
  }, []);

  const fetchProfiles = useCallback(async () => {
    try {
      const data = await apiFetch('/org/speakers');
      if (data) {
        setSpeakerProfiles(data.map((p: any) => ({
          id: p.id,
          name: p.name,
          user_id: p.user_id,
        })));
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchProfiles();
    fetchSessions();

    // Auto-poll sessions every 2 seconds to keep logs fresh in real time
    const interval = setInterval(fetchSessions, 2000);
    return () => clearInterval(interval);
  }, [fetchProfiles, fetchSessions]);

  // Fast staggered fetch when monitoring stops
  const handleStopMonitoring = useCallback(() => {
    // Optimistically update session log immediately with current session
    if (riskData?.session_id) {
      const shortId = riskData.session_id.slice(0, 5);
      const score = riskData.score || 0.08;
      sessionScoresCacheRef.current[shortId] = score;

      const currentFinalSession: SessionLogItem = {
        id: `#${shortId}`,
        caller: riskData.profile_name ? `Stream (${riskData.profile_name})` : 'Live Stream',
        status: 'ended',
        risk: score,
        dur: `${recordingTime}s active`,
        timestamp: new Date().toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        }) + ' IST',
      };

      setDbSessions((prev) => [
        currentFinalSession,
        ...prev.filter((p) => !p.id.includes(shortId)),
      ]);
    }

    stopMonitoring();

    // Rapid DB re-queries to guarantee latest committed score from PostgreSQL
    setTimeout(fetchSessions, 200);
    setTimeout(fetchSessions, 600);
    setTimeout(fetchSessions, 1200);
    setTimeout(fetchSessions, 2500);
  }, [riskData, recordingTime, stopMonitoring, fetchSessions]);

  const handleStartMonitoring = (file?: File | React.MouseEvent) => {
    const profId = selectedProfileId || undefined;
    if (file && file instanceof File) {
      startMonitoring(file, profId);
    } else {
      startMonitoring(undefined, profId);
    }
  };

  // Preserve last valid score when stopped
  const currentScore = riskData ? riskData.score : 0.08;
  const deepfakeSubScore = riskData ? riskData.raw_components.deepfake : 0.05;
  const speakerMatchScore = riskData && riskData.has_enrollment ? riskData.raw_components.speaker_match : null;
  const speakerSubScore = riskData && riskData.has_enrollment ? max(0, 1.0 - riskData.raw_components.speaker_match) : 0.0;
  const prosodySubScore = riskData ? riskData.raw_components.prosody : 0.10;
  const latencyMs = riskData ? riskData.latency_ms : 0;
  const isHighRisk = currentScore >= 0.6;

  const triggerCountermeasure = (action: string) => {
    setCountermeasureStatus(`Action Initiated: ${action} — Session Terminated`);
    handleStopMonitoring();
    setTimeout(() => setCountermeasureStatus(null), 6000);
  };

  function max(a: number, b: number) { return a > b ? a : b; }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60).toString().padStart(2, '0');
    const sec = (s % 60).toString().padStart(2, '0');
    return `${m}:${sec}`;
  };

  return (
    <>
      <div className="min-h-screen pt-20 pb-8 px-4 sm:px-6">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
          >
            <div>
              <h1 className="text-2xl font-bold text-[var(--color-sentinel-text)] flex items-center gap-2">
                Monitoring Dashboard
                {riskData?.profile_name && (
                  <span className="text-xs px-2.5 py-1 rounded-lg bg-[rgba(0,229,200,0.12)] text-[var(--color-accent-primary)] font-semibold border border-[rgba(0,229,200,0.2)]">
                    Target Speaker: {riskData.profile_name}
                  </span>
                )}
              </h1>
              <p className="text-sm text-[var(--color-sentinel-text-muted)] mt-0.5">
                {isMonitoring
                  ? `Live WebSocket stream active (${isConnected ? 'Backend Connected' : 'Connecting...'}) — ${formatTime(recordingTime)}`
                  : 'Select an enrolled speaker profile (optional) and click Start Monitoring'
                }
              </p>
              {error && (
                <p className="text-xs text-red-400 font-semibold mt-1 flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-red-400" /> {error}
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Speaker Profile Selector Dropdown */}
              <div className="relative">
                <select
                  value={selectedProfileId}
                  onChange={(e) => setSelectedProfileId(e.target.value)}
                  disabled={isMonitoring}
                  className={`px-3 py-2.5 rounded-xl border text-xs font-semibold focus:outline-none transition-all ${
                    isMonitoring
                      ? 'bg-[var(--color-sentinel-surface-2)] text-[var(--color-sentinel-text-dim)] border-[var(--color-sentinel-border)] cursor-not-allowed'
                      : 'bg-[var(--color-sentinel-surface)] text-[var(--color-sentinel-text)] border-[var(--color-sentinel-border)] hover:border-[var(--color-accent-primary)]'
                  }`}
                >
                  <option value="">General Detection (No Enrolled Profile)</option>
                  {speakerProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      Speaker Profile: {p.name} ({p.user_id})
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={() => setShowUpload(true)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--color-sentinel-border)] text-sm font-medium text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:border-[var(--color-sentinel-text-dim)] transition-all"
              >
                <Upload className="w-4 h-4" />
                Upload File
              </button>

              <button
                onClick={isMonitoring ? handleStopMonitoring : handleStartMonitoring}
                className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 ${
                  isMonitoring
                    ? 'bg-[var(--color-sentinel-surface-3)] text-[var(--color-risk-critical)] border border-[var(--color-risk-critical)] shadow-lg hover:bg-[rgba(239,68,68,0.1)]'
                    : 'bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] shadow-lg hover:brightness-110'
                }`}
                style={{
                  boxShadow: isMonitoring
                    ? 'none'
                    : '0 6px 24px rgba(0,229,200,0.2)',
                }}
              >
                {isMonitoring ? (
                  <>
                    <Square className="w-4 h-4" />
                    Stop · {formatTime(recordingTime)}
                  </>
                ) : (
                  <>
                    <Mic className="w-4 h-4" />
                    Start Monitoring
                  </>
                )}
              </button>
            </div>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="mb-6"
          >
            <StatsBar isMonitoring={isMonitoring} isConnected={isConnected} latencyMs={latencyMs} />
          </motion.div>

          {/* File Playback Complete — 10s Grace Action Window */}
          <AnimatePresence>
            {graceCountdown !== null && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mb-6 rounded-2xl border border-[var(--color-risk-medium)] bg-[rgba(245,197,66,0.08)] p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-lg"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-[rgba(245,197,66,0.15)] flex items-center justify-center shrink-0">
                    <Clock className="w-5 h-5 text-[var(--color-risk-medium)] animate-pulse" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-[var(--color-risk-medium)] uppercase tracking-wider flex items-center gap-2">
                      Audio Analysis Complete · Action Window Open
                    </h4>
                    <p className="text-xs text-[var(--color-sentinel-text-muted)] mt-0.5">
                      Uploaded file finished playing. Results will automatically save and close in <strong className="text-[var(--color-risk-medium)] font-mono text-sm">{graceCountdown}s</strong>. Take relevant countermeasures or dismiss.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="px-3 py-1 rounded-lg bg-[var(--color-sentinel-surface-3)] text-xs font-mono font-bold text-[var(--color-risk-medium)] border border-[var(--color-risk-medium)]">
                    Closing in {graceCountdown}s
                  </span>
                  <button
                    onClick={handleStopMonitoring}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-3)] transition-colors border border-[var(--color-sentinel-border)]"
                  >
                    Dismiss Now
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Actionable Risk Countermeasure Banner (High Risk Warning) */}
          <AnimatePresence>
            {(isHighRisk || countermeasureStatus) && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="mb-6 rounded-2xl border border-[var(--color-risk-critical)] bg-[rgba(239,68,68,0.08)] p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl"
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center shrink-0">
                    <ShieldAlert className="w-6 h-6 text-red-400 animate-pulse" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-red-400 uppercase tracking-wider flex items-center gap-2">
                      High Impersonation Risk Alert Detected ({ (currentScore * 100).toFixed(0) }%)
                    </h3>
                    <p className="text-xs text-[var(--color-sentinel-text-muted)] mt-0.5 leading-relaxed">
                      {riskData?.alert_reason || 'Synthetic voice signatures or speaker identity mismatch detected. Immediate secondary verification recommended before approving sensitive financial operations.'}
                    </p>
                    {countermeasureStatus && (
                      <p className="text-xs font-bold text-[var(--color-accent-primary)] mt-1.5 animate-bounce">
                        ✓ {countermeasureStatus}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Persistent Dashboard Grid */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Left — Audio + Sessions */}
              <div className="lg:col-span-8 flex flex-col gap-5">
                {/* Audio */}
                <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)]">Live Audio Stream</h3>
                    <div className="flex items-center gap-2.5 text-[10px]">
                      {isMonitoring && (
                        <button
                          onClick={handleStopMonitoring}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-500/20 border border-red-500/40 text-red-300 font-bold hover:bg-red-500/30 transition-all text-xs cursor-pointer shadow-sm"
                        >
                          <Square className="w-3 h-3 text-red-400 fill-red-400" /> Stop Stream
                        </button>
                      )}
                      <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full font-semibold ${
                        isMonitoring
                          ? 'bg-[rgba(0,229,200,0.1)] text-[var(--color-risk-low)]'
                          : 'bg-[var(--color-sentinel-surface-3)] text-[var(--color-sentinel-text-dim)]'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${isMonitoring ? 'bg-[var(--color-risk-low)] animate-pulse' : 'bg-[var(--color-sentinel-text-dim)]'}`} />
                        {isMonitoring ? (isConnected ? 'Backend Streaming Active' : 'Connecting WebSocket') : 'Idle / Stopped'}
                      </span>
                      <span className="text-[var(--color-sentinel-text-dim)]">16kHz · Mono PCM</span>
                    </div>
                  </div>
                  <AudioVisualizer isActive={isMonitoring} variant="waveform" height={140} />
                  <div className="mt-3">
                    <AudioVisualizer isActive={isMonitoring} variant="bars" height={70} />
                  </div>
                </div>

                {/* Session Logs */}
                <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 min-h-[380px] max-h-[460px] overflow-y-auto flex flex-col justify-between">
                  <SessionsPanel isMonitoring={isMonitoring} sessionId={riskData?.session_id} liveRiskScore={currentScore} sessions={dbSessions} />
                </div>
              </div>

              {/* Right — Gauge + Alerts */}
              <div className="lg:col-span-4 flex flex-col gap-5">
                {/* Gauge */}
                <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 flex flex-col items-center">
                  <div className="flex items-center justify-between w-full mb-2">
                    <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)]">Impersonation Risk Score</h3>
                    <span className="text-[9px] text-[var(--color-sentinel-text-dim)] px-2 py-0.5 rounded bg-[var(--color-sentinel-surface-3)]">
                      EMA α=0.3
                    </span>
                  </div>
                  <RiskGauge score={currentScore} size={220} />

                  {/* Sub-scores */}
                  <div className="flex items-center gap-4 mt-2 transition-opacity duration-300 w-full justify-center">
                    {[
                      { label: 'Deepfake Prob', v: deepfakeSubScore, c: 'var(--color-accent-primary)' },
                      { 
                        label: riskData?.has_enrollment ? `Speaker Match (${(speakerMatchScore! * 100).toFixed(0)}%)` : 'Speaker Verification', 
                        v: speakerSubScore, 
                        c: 'var(--color-accent-purple)',
                        disabled: !riskData?.has_enrollment 
                      },
                      { label: 'Prosody Anomaly', v: prosodySubScore, c: 'var(--color-risk-medium)' },
                    ].map(s => (
                      <div key={s.label} className="flex flex-col items-center gap-1">
                        <span className="text-[9px] text-[var(--color-sentinel-text-dim)] text-center leading-tight truncate max-w-[85px]">{s.label}</span>
                        <div className="w-14 h-1.5 rounded-full bg-[var(--color-sentinel-surface-3)] overflow-hidden">
                          <motion.div
                            className="h-full rounded-full"
                            style={{ background: s.c }}
                            animate={{ width: `${Math.min(s.v * 100, 100)}%` }}
                            transition={{ duration: 0.5 }}
                          />
                        </div>
                        <span className="text-[10px] font-bold text-[var(--color-sentinel-text-muted)]">
                          {s.disabled ? 'Unlinked' : `${(s.v * 100).toFixed(0)}%`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Alerts */}
                <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 min-h-[380px] max-h-[460px] overflow-y-auto">
                  <AlertsPanel alerts={alerts} />
                </div>
              </div>
            </div>

            {/* Scoring formula */}
            <div className="mt-5 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5">
              <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)] mb-3">Ensemble Model Breakdown</h3>
              <div className="bg-[var(--color-sentinel-surface-2)] rounded-xl p-4 text-sm text-[var(--color-sentinel-text-muted)] overflow-x-auto font-mono text-xs">
                <div>
                  <span className="text-[var(--color-accent-primary)] font-semibold">S_ensemble</span> = 
                  {riskData?.has_enrollment 
                    ? ' 0.40×AASIST/XLS-R + 0.35×ECAPA-TDNN (Speaker Verification) + 0.15×Prosody + 0.10×SpeakerDrift'
                    : ' 0.60×AASIST/XLS-R (Deepfake) + 0.30×Prosody (Forensics) + 0.10×SpeakerDrift [Adaptive Re-normalized Mode]'
                  }
                </div>
                <div className="mt-2 text-[var(--color-sentinel-text-dim)]">
                  {riskData ? (
                    <>AASIST: {riskData.model_detail.aasist_score ?? 'N/A'} | XLS-R: {riskData.model_detail.xlsr_score ?? 'N/A'} | ECAPA Sim: {riskData.model_detail.speaker_similarity !== undefined ? `${(riskData.model_detail.speaker_similarity * 100).toFixed(1)}%` : 'N/A'} | Jitter: {riskData.model_detail.prosody.jitter} | HNR: {riskData.model_detail.prosody.hnr} dB</>
                  ) : (
                    'AASIST (Graph Attention) + XLS-R 300M (Multilingual SSL) + ECAPA-TDNN + Parselmouth Prosody'
                  )}
                </div>
              </div>
            </div>

            {/* Live Model Inference Logs Terminal */}
            <div className="mt-5 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5">
              <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)] mb-3 flex items-center gap-2">
                Live Pipeline Logs <span className="animate-pulse w-2 h-2 rounded-full bg-[var(--color-risk-low)]"></span>
              </h3>
              <div className="bg-[#1e1e2e] rounded-xl p-4 h-64 overflow-y-auto font-mono text-xs text-[#a6accd] flex flex-col gap-2">
                {modelLogs.length === 0 ? (
                   <span className="text-gray-500 italic">Waiting for audio stream...</span>
                ) : (
                  modelLogs.map((log, idx) => (
                    <div key={`${log.timestamp}-${log.chunk_index}-${idx}`} className="border-b border-[#313244] pb-2 mb-2 last:border-0 last:mb-0 last:pb-0">
                      <span className="text-[#89b4fa]">[{log.timestamp}]</span> <span className="text-[#cba6f7]">Chunk #{log.chunk_index}</span>
                      <br/>
                      <span className="text-[#f38ba8]">Deepfake (AASIST):</span> {log.details.aasist_score?.toFixed(4) ?? 'N/A'} | <span className="text-[#f38ba8]">XLS-R:</span> {log.details.xlsr_score?.toFixed(4) ?? 'N/A'}
                      <br/>
                      <span className="text-[#a6e3a1]">Speaker:</span> Verified: {log.details.speaker_verified ? 'Yes' : 'No'} | Sim: {log.details.speaker_similarity !== undefined ? log.details.speaker_similarity.toFixed(4) : 'N/A'}
                      <br/>
                      <span className="text-[#f9e2af]">Prosody:</span> f0_mean: {log.details.prosody.f0_mean.toFixed(2)}, jitter: {log.details.prosody.jitter.toFixed(4)}, hnr: {log.details.prosody.hnr.toFixed(2)}
                    </div>
                  ))
                )}
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Upload Modal */}
      <AnimatePresence>
        {showUpload && (
          <UploadModal
            onClose={() => setShowUpload(false)}
            onAnalyze={(file) => {
              handleStartMonitoring(file);
            }}
          />
        )}
      </AnimatePresence>
    </>
  );
}
