import { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Upload, Square, X, FileAudio, AlertTriangle, Clock, Zap, Radio, WifiOff, ShieldAlert, ShieldCheck, Info, ChevronRight, Activity, Cpu, Wifi, TrendingDown } from 'lucide-react';
import AudioVisualizer from '../components/dashboard/AudioVisualizer';
import { useAudioStreamer } from '../hooks/useAudioStreamer';

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
   Sessions Panel
   ======================================== */
function SessionsPanel({ isMonitoring, sessionId, sessions: propSessions }: { isMonitoring: boolean; sessionId?: string; sessions: { id: string; caller: string; status: 'active' | 'monitoring' | 'ended'; risk: number; dur: string }[] }) {
  const sessions = isMonitoring && sessionId
    ? [
        { id: `#${sessionId.slice(0, 5)}`, caller: 'Live Microphone Stream', status: 'active' as const, risk: 0.15, dur: 'Live' },
        ...propSessions,
      ]
    : propSessions;

  const statusCfg = {
    active: { label: 'LIVE', color: 'var(--color-risk-low)', pulse: true },
    monitoring: { label: 'OK', color: 'var(--color-risk-low)', pulse: true },
    ended: { label: 'ENDED', color: 'var(--color-sentinel-text-dim)', pulse: false },
  };

  const riskColor = (r: number) =>
    r < 0.3 ? 'var(--color-risk-low)' : r < 0.6 ? 'var(--color-risk-medium)' : r < 0.8 ? 'var(--color-risk-high)' : 'var(--color-risk-critical)';

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)]">Active Sessions</h3>
        <span className="flex items-center gap-1 text-[10px] text-[var(--color-risk-low)]">
          <Radio className={`w-3 h-3 ${isMonitoring ? 'animate-pulse' : ''}`} /> {isMonitoring ? 'Live Analysis' : 'Session Ready'}
        </span>
      </div>
      {sessions.length === 0 ? (
        <div className="text-center py-6 text-xs text-[var(--color-sentinel-text-dim)]">
          No sessions recorded yet.
        </div>
      ) : (
      <div className="flex flex-col gap-2">
        {sessions.map((s, i) => {
          const cfg = statusCfg[s.status];
          return (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-3 p-3 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] hover:border-[var(--color-sentinel-border)] transition-colors cursor-pointer group"
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                s.status === 'active' ? 'bg-[rgba(0,229,200,0.12)]' : 'bg-[var(--color-sentinel-surface-3)]'
              }`}>
                {s.status === 'ended'
                  ? <WifiOff className="w-3.5 h-3.5 text-[var(--color-sentinel-text-dim)]" />
                  : <Mic className="w-3.5 h-3.5 text-[var(--color-accent-primary)]" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-[var(--color-sentinel-text)]">Session {s.id}</span>
                  <span className="flex items-center gap-1 text-[9px] font-bold" style={{ color: cfg.color }}>
                    <span className={`w-1.5 h-1.5 rounded-full ${cfg.pulse ? 'animate-pulse' : ''}`} style={{ background: cfg.color }} />
                    {cfg.label}
                  </span>
                </div>
                <p className="text-[10px] text-[var(--color-sentinel-text-dim)] truncate">{s.caller}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0 text-[10px]">
                <span className="text-[var(--color-sentinel-text-dim)]">{s.dur}</span>
                <span className="font-bold flex items-center gap-0.5" style={{ color: riskColor(s.risk) }}>
                  <Zap className="w-3 h-3" /> {s.risk.toFixed(2)}
                </span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-[var(--color-sentinel-text-dim)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
            </motion.div>
          );
        })}
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
    if (alerts.length > 0) return alerts;
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
            if (dismissed.has(i)) return null;
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
    recordingTime,
    error,
    startMonitoring,
    stopMonitoring,
  } = useAudioStreamer();

  const [showUpload, setShowUpload] = useState(false);
  const [hasProfiles, setHasProfiles] = useState(false);
  const [noProfileWarning, setNoProfileWarning] = useState(false);
  const [dbSessions, setDbSessions] = useState<{ id: string; caller: string; status: 'active' | 'monitoring' | 'ended'; risk: number; dur: string }[]>([]);

  useEffect(() => {
    // Check if there are speaker profiles
    const checkProfiles = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/v1/speakers');
        if (res.ok) {
          const data = await res.json();
          setHasProfiles(data.length > 0);
        }
      } catch { /* ignore */ }
    };
    // Fetch sessions
    const fetchSessions = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/v1/sessions');
        if (res.ok) {
          const data = await res.json();
          setDbSessions(data.map((s: any) => ({
            id: `#${String(s.session_id).slice(0, 5)}`,
            caller: s.caller_id || 'Unknown Caller',
            status: (s.status === 'active' ? 'active' : 'ended') as 'active' | 'ended',
            risk: 0,
            dur: s.end_time
              ? `${Math.round((new Date(s.end_time).getTime() - new Date(s.start_time).getTime()) / 60000)}:${String(Math.round((new Date(s.end_time).getTime() - new Date(s.start_time).getTime()) / 1000) % 60).padStart(2, '0')}`
              : 'Live',
          })));
        }
      } catch { /* ignore */ }
    };
    checkProfiles();
    fetchSessions();
  }, [isMonitoring]);

  const handleStartMonitoring = (file?: File | React.MouseEvent) => {
    if (!hasProfiles) {
      setNoProfileWarning(true);
      setTimeout(() => setNoProfileWarning(false), 4000);
      return;
    }
    if (file && file instanceof File) {
      startMonitoring(file);
    } else {
      startMonitoring();
    }
  };

  // Preserve last valid score when stopped
  const currentScore = riskData ? riskData.score : 0.12;
  const deepfakeSubScore = riskData ? riskData.raw_components.deepfake : 0.10;
  const speakerSubScore = riskData ? 1.0 - riskData.raw_components.speaker_match : 0.05;
  const prosodySubScore = riskData ? riskData.raw_components.prosody : 0.15;
  const latencyMs = riskData ? riskData.latency_ms : 0;

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
              <h1 className="text-2xl font-bold text-[var(--color-sentinel-text)]">
                Monitoring Dashboard
              </h1>
              <p className="text-sm text-[var(--color-sentinel-text-muted)] mt-0.5">
                {isMonitoring
                  ? `Live WebSocket stream active (${isConnected ? 'Backend Connected' : 'Connecting...'}) — ${formatTime(recordingTime)}`
                  : 'Click Start Monitoring to connect live microphone stream to VoiceGuardAI ML backend'
                }
              </p>
              {error && (
                <p className="text-xs text-red-400 font-semibold mt-1 flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-red-400" /> {error}
                </p>
              )}
              {noProfileWarning && (
                <p className="text-xs text-amber-400 font-semibold mt-1 flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> You must enroll at least one speaker profile before starting monitoring.
                </p>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowUpload(true)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--color-sentinel-border)] text-sm font-medium text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:border-[var(--color-sentinel-text-dim)] transition-all"
              >
                <Upload className="w-4 h-4" />
                Upload
              </button>

              <button
                onClick={isMonitoring ? stopMonitoring : handleStartMonitoring}
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
                    <div className="flex items-center gap-2 text-[10px]">
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

                {/* Sessions */}
                <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5">
                  <SessionsPanel isMonitoring={isMonitoring} sessionId={riskData?.session_id} sessions={dbSessions} />
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
                  <div className="flex items-center gap-5 mt-2 transition-opacity duration-300 w-full justify-center">
                    {[
                      { label: 'Deepfake', v: deepfakeSubScore, c: 'var(--color-accent-primary)' },
                      { label: 'Speaker Mismatch', v: speakerSubScore, c: 'var(--color-accent-purple)' },
                      { label: 'Prosody Anomaly', v: prosodySubScore, c: 'var(--color-risk-medium)' },
                    ].map(s => (
                      <div key={s.label} className="flex flex-col items-center gap-1">
                        <span className="text-[9px] text-[var(--color-sentinel-text-dim)]">{s.label}</span>
                        <div className="w-14 h-1.5 rounded-full bg-[var(--color-sentinel-surface-3)] overflow-hidden">
                          <motion.div
                            className="h-full rounded-full"
                            style={{ background: s.c }}
                            animate={{ width: `${Math.min(s.v * 100, 100)}%` }}
                            transition={{ duration: 0.5 }}
                          />
                        </div>
                        <span className="text-[10px] font-bold text-[var(--color-sentinel-text-muted)]">
                          {(s.v * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Alerts */}
                <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 flex-1 max-h-[460px] overflow-y-auto">
                  <AlertsPanel alerts={alerts} />
                </div>
              </div>
            </div>

            {/* Scoring formula */}
            <div className="mt-5 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5">
              <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)] mb-3">Ensemble Model Breakdown</h3>
              <div className="bg-[var(--color-sentinel-surface-2)] rounded-xl p-4 text-sm text-[var(--color-sentinel-text-muted)] overflow-x-auto font-mono text-xs">
                <div><span className="text-[var(--color-accent-primary)] font-semibold">S_ensemble</span> = 0.40×AASIST/XLS-R + 0.25×ECAPA-TDNN + 0.15×Prosody + 0.10×SpeakerDrift</div>
                <div className="mt-2 text-[var(--color-sentinel-text-dim)]">
                  {riskData ? (
                    <>AASIST: {riskData.model_detail.aasist_score ?? 'N/A'} | XLS-R: {riskData.model_detail.xlsr_score ?? 'N/A'} | Jitter: {riskData.model_detail.prosody.jitter} | HNR: {riskData.model_detail.prosody.hnr} dB</>
                  ) : (
                    'AASIST (Graph Attention) + XLS-R 300M (Multilingual SSL) + ECAPA-TDNN + Parselmouth Prosody'
                  )}
                </div>
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
