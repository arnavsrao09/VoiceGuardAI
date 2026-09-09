import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Square,
  X,
  FileAudio,
  AlertTriangle,
  Clock,
  Zap,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Info,
  Mic,
  Activity,
  Cpu,
  Terminal,
  FileSpreadsheet,
  Fingerprint,
  MessageSquare
} from 'lucide-react';
import AudioVisualizer from '../components/dashboard/AudioVisualizer';
import LiveCallIntelligenceStudio from '../components/dashboard/LiveCallIntelligenceStudio';
import TransactionInterceptor from '../components/dashboard/TransactionInterceptor';
import ForensicAcousticRadar from '../components/dashboard/ForensicAcousticRadar';
import { useAudioStreamer, type LiveRiskData } from '../hooks/useAudioStreamer';
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
const BENCHMARK_SAMPLES = [
  { name: 'Indian English', file: 'indian_english_high_value.wav', flag: '🇮🇳', region: 'Mumbai Accent', lang: 'English' },
  { name: 'Hindi Dialect', file: 'hindi_accent_bank_transfer.wav', flag: '🇮🇳', region: 'Delhi Accent', lang: 'हिन्दी' },
  { name: 'Telugu Dialect', file: 'telugu_urgent_wire.wav', flag: '🇮🇳', region: 'Hyderabad Accent', lang: 'తెలుగు' },
  { name: 'Tamil Dialect', file: 'tamil_otp_override.wav', flag: '🇮🇳', region: 'Chennai Accent', lang: 'தமிழ்' },
  { name: 'Kannada Dialect', file: 'kannada_beneficiary_add.wav', flag: '🇮🇳', region: 'Bengaluru Accent', lang: 'ಕನ್ನಡ' },
  { name: 'Bengali Dialect', file: 'bengali_corporate_swift.wav', flag: '🇮🇳', region: 'Kolkata Accent', lang: 'বাংলা' },
];

function UploadModal({ onClose, onAnalyze }: { onClose: () => void; onAnalyze: (file: File) => void }) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [invalidFile, setInvalidFile] = useState(false);
  const [loadingBenchmark, setLoadingBenchmark] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleBenchmarkSelect = async (sample: typeof BENCHMARK_SAMPLES[0]) => {
    setLoadingBenchmark(sample.file);
    try {
      const res = await fetch(`/samples/${sample.file}`);
      const blob = await res.blob();
      const loadedFile = new File([blob], sample.file, { type: 'audio/wav' });
      setFile(loadedFile);
      setInvalidFile(false);
    } catch (err) {
      console.error('Failed to load benchmark audio:', err);
    } finally {
      setLoadingBenchmark(null);
    }
  };

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
        className="w-full max-w-lg rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-6 max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-[var(--color-sentinel-text)]">Upload Audio File</h3>
            <p className="text-xs text-[var(--color-sentinel-text-dim)]">Upload custom audio or choose an Indian dialect benchmark</p>
          </div>
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
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 ${
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
              <AlertTriangle className="w-8 h-8 text-red-500" />
              <p className="text-sm font-semibold text-red-400">Invalid file format</p>
              <p className="text-xs text-[var(--color-sentinel-text-dim)]">Only .wav, .mp3, .flac, .ogg are supported</p>
            </div>
          ) : file ? (
            <div className="flex flex-col items-center gap-2">
              <FileAudio className="w-8 h-8 text-[var(--color-accent-primary)]" />
              <p className="text-sm font-semibold text-[var(--color-sentinel-text)] truncate max-w-xs">{file.name}</p>
              <p className="text-xs text-[var(--color-sentinel-text-dim)]">Ready for ML pipeline analysis</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className={`w-8 h-8 ${dragging ? 'text-[var(--color-accent-primary)]' : 'text-[var(--color-sentinel-text-dim)]'}`} />
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

        {/* Multi-Lingual Accent & Dialect Benchmark Test Suite */}
        <div className="mt-4 pt-3.5 border-t border-[var(--color-sentinel-border-subtle)]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-sentinel-text-dim)]">
              Multi-Lingual Accent Benchmark Suite
            </span>
            <span className="text-[10px] text-[var(--color-accent-primary)] font-mono font-semibold">
              6 Regional Audio Samples
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {BENCHMARK_SAMPLES.map((sample) => {
              const isSelected = file?.name === sample.file;
              const isLoading = loadingBenchmark === sample.file;
              return (
                <button
                  key={sample.file}
                  type="button"
                  onClick={() => handleBenchmarkSelect(sample)}
                  className={`p-2 rounded-xl border text-left transition-all ${
                    isSelected
                      ? 'bg-[var(--color-accent-primary-dim)] border-[var(--color-accent-primary)] ring-1 ring-[var(--color-accent-primary)]'
                      : 'bg-[var(--color-sentinel-surface-2)] border-[var(--color-sentinel-border-subtle)] hover:border-[var(--color-accent-primary)]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[var(--color-sentinel-text)]">
                      {sample.name}
                    </span>
                    <span className="text-[10px]">{sample.flag}</span>
                  </div>
                  <div className="flex items-center justify-between mt-1 text-[10px] text-[var(--color-sentinel-text-dim)]">
                    <span>{sample.region}</span>
                    <span className="font-mono text-[var(--color-accent-primary)]">{isLoading ? '...' : sample.lang}</span>
                  </div>
                </button>
              );
            })}
          </div>
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
                ? 'bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] hover:brightness-110 shadow-lg'
                : 'bg-[var(--color-sentinel-surface-3)] text-[var(--color-sentinel-text-dim)] cursor-not-allowed'
            }`}
          >
            Analyze Audio Sample
          </button>
        </div>
      </motion.div>
    </motion.div>
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
    updateMetadata,
  } = useAudioStreamer();

  const [showUpload, setShowUpload] = useState(false);
  const [speakerProfiles, setSpeakerProfiles] = useState<{ id: string; name: string; user_id: string }[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>('');
  const [selectedLocation, setSelectedLocation] = useState<string>('Local Network (IN)');
  const [selectedAmount, setSelectedAmount] = useState<number>(50000);
  const [selectedTransferType, setSelectedTransferType] = useState<string>('High-Value Wire Transfer');
  const [selectedPhone, setSelectedPhone] = useState<string>('+91 98200 12345');
  const [isExtractedFromSpeech, setIsExtractedFromSpeech] = useState<boolean>(false);
  const [isInterceptorOpen, setIsInterceptorOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'intelligence' | 'forensics' | 'history' | 'terminal'>('intelligence');

  const handleLiveIntentExtracted = useCallback((intent: {
    amount?: number | null;
    channel?: string;
    urgencyLevel?: string;
    summary?: string;
  }) => {
    if (intent.amount && intent.amount > 0) {
      setSelectedAmount(intent.amount);
      setIsExtractedFromSpeech(true);
      updateMetadata({ amount: intent.amount });
    }
    if (intent.channel) {
      setSelectedTransferType(intent.channel);
      setIsExtractedFromSpeech(true);
      updateMetadata({ transfer_type: intent.channel });
    }
  }, [updateMetadata]);
  const [countermeasureStatus, setCountermeasureStatus] = useState<string | null>(null);
  const [dbSessions, setDbSessions] = useState<SessionLogItem[]>([]);
  const sessionScoresCacheRef = useRef<Record<string, number>>({});
  const dismissedSessionsRef = useRef<Set<string>>(new Set());
  const poppedSessionsRef = useRef<Set<string>>(new Set());

  // Real-time telephony call state (Zoiper mobile/desktop, Asterisk PBX)
  const [telemetryRiskData, setTelemetryRiskData] = useState<LiveRiskData | null>(null);
  const [isTelephonyActive, setIsTelephonyActive] = useState<boolean>(false);
  const [telephonyCaller, setTelephonyCaller] = useState<string>('Live Softphone');

  // Connect to backend TelemetryHub for instant real-time fan-out from phone calls & SIP media
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let isCancelled = false;

    const connect = () => {
      if (isCancelled) return;
      try {
        ws = new WebSocket('ws://localhost:8000/ws/telemetry');
        ws.onopen = () => {
          console.log('[Dashboard] Subscribed to backend live telemetry stream (/ws/telemetry)');
        };
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'session_ended') {
              setIsTelephonyActive(false);
              setTelemetryRiskData(null);
              return;
            }
            if (data.score !== undefined) {
              setTelemetryRiskData(data);
              setIsTelephonyActive(true);
              if (data.caller_phone || data.caller_id) {
                setTelephonyCaller(data.caller_phone || data.caller_id);
              }
            }
          } catch (err) {
            console.error('[Dashboard] Telemetry parse error:', err);
          }
        };
        ws.onclose = () => {
          if (!isCancelled) {
            reconnectTimer = window.setTimeout(connect, 2000);
          }
        };
        ws.onerror = () => {
          try { ws?.close(); } catch {}
        };
      } catch (err) {
        if (!isCancelled) {
          reconnectTimer = window.setTimeout(connect, 2000);
        }
      }
    };

    connect();

    return () => {
      isCancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        try { ws.close(); } catch {}
      }
    };
  }, []);

  // Auto-open Security Interceptor Modal on HIGH / CRITICAL alerts (once per session; no re-popping if dismissed)
  useEffect(() => {
    const active = riskData || telemetryRiskData;
    if (active && (active.should_alert || active.level === 'CRITICAL' || active.level === 'HIGH')) {
      const sessId = active.session_id || 'active-session';
      if (dismissedSessionsRef.current.has(sessId)) {
        return;
      }
      if (!poppedSessionsRef.current.has(sessId)) {
        poppedSessionsRef.current.add(sessId);
        setIsInterceptorOpen(true);
      }
    }
  }, [riskData, telemetryRiskData]);

  const handleCloseInterceptor = useCallback(() => {
    const active = riskData || telemetryRiskData;
    const sessId = active?.session_id || 'active-session';
    dismissedSessionsRef.current.add(sessId);
    setIsInterceptorOpen(false);
  }, [riskData, telemetryRiskData]);

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

  // A browser microphone stream carries profile_id directly in its WebSocket
  // URL. SIP media uses a separate server-side WebSocket, so explicitly pass
  // the dashboard selection to the SIP gateway before the caller dials.
  useEffect(() => {
    apiFetch('/telephony/sip/target-profile', {
      method: 'PUT',
      body: JSON.stringify({ profile_id: selectedProfileId || null }),
    }).catch((err) => {
      console.warn('[Dashboard] Could not set SIP target profile:', err);
    });
  }, [selectedProfileId]);

  // Fast staggered fetch when monitoring stops
  const handleStopMonitoring = useCallback(() => {
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

    setTimeout(fetchSessions, 200);
    setTimeout(fetchSessions, 600);
    setTimeout(fetchSessions, 1200);
    setTimeout(fetchSessions, 2500);
  }, [riskData, recordingTime, stopMonitoring, fetchSessions]);

  const handleStartMonitoring = (file?: File | React.MouseEvent) => {
    if (isMonitoring) return;
    const profId = selectedProfileId || undefined;
    const context = {
      location: selectedLocation,
      amount: selectedAmount,
      transferType: selectedTransferType,
      callerPhone: selectedPhone,
    };
    if (file && file instanceof File) {
      startMonitoring(file, profId, context);
    } else {
      startMonitoring(undefined, profId, context);
    }
  };

  // Active risk data from either local mic or real-time telephony stream
  const activeRiskData = isMonitoring ? riskData : (isTelephonyActive ? telemetryRiskData : null);
  const isAnyMonitoring = isMonitoring || isTelephonyActive;

  const DEFAULT_IDLE_SCORE = 0.00;
  const currentScore = isAnyMonitoring && activeRiskData ? activeRiskData.score : DEFAULT_IDLE_SCORE;
  const deepfakeSubScore = isAnyMonitoring && activeRiskData ? activeRiskData.raw_components.deepfake : 0.00;
  const speakerMatchScore = isAnyMonitoring && activeRiskData && activeRiskData.has_enrollment ? activeRiskData.raw_components.speaker_match : null;
  const prosodySubScore = isAnyMonitoring && activeRiskData ? activeRiskData.raw_components.prosody : 0.00;
  const latencyMs = isAnyMonitoring && activeRiskData ? activeRiskData.latency_ms : 0;
  const isHighRisk = isAnyMonitoring && currentScore >= 0.6;

  const triggerCountermeasure = async (action: string) => {
    const actionMap: Record<string, string> = {
      "Voice Callback Initiated": "INITIATE_CALLBACK",
      "Push MFA Sent to Enrolled Mobile": "REQUIRE_DUAL_SUPERVISOR_APPROVAL",
      "Escalated to Supervisor Security Desk": "REQUIRE_DUAL_SUPERVISOR_APPROVAL",
      "Hold Transaction": "AUTO_HOLD_TRANSACTION",
      "Block Channel": "BLOCK_CHANNEL",
    };
    const mappedAction = actionMap[action] || "AUTO_HOLD_TRANSACTION";
    try {
      await apiFetch('/alerts/workflows/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: mappedAction,
          session_id: riskData?.session_id,
          caller_id: riskData?.profile_name ? `${selectedPhone} (${riskData.profile_name})` : selectedPhone,
          amount: selectedAmount,
          reason: riskData?.alert_reason || 'Manual countermeasure triggered from Forensic Dashboard',
        }),
      });
    } catch (e) {
      console.error('Countermeasure dispatch error:', e);
    }
    setCountermeasureStatus(`Action Executed: ${action} — Session Status Updated`);
    handleStopMonitoring();
    setTimeout(() => setCountermeasureStatus(null), 6000);
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60).toString().padStart(2, '0');
    const sec = (s % 60).toString().padStart(2, '0');
    return `${m}:${sec}`;
  };

  const getRiskBadgeColor = (score: number) => {
    if (score < 0.30) return { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', label: 'LOW THREAT' };
    if (score < 0.60) return { text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20', label: 'ELEVATED' };
    if (score < 0.80) return { text: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20', label: 'HIGH RISK' };
    return { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20', label: 'CRITICAL' };
  };

  const threatBadge = getRiskBadgeColor(currentScore);

  return (
    <>
      <div className="min-h-screen pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-[1440px] mx-auto">
        {/* Error Banner */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Grace Countdown Banner */}
        <AnimatePresence>
          {graceCountdown !== null && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between gap-3 shadow-md"
            >
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-400 animate-spin" />
                <span>Playback finished. Results auto-saving in <strong>{graceCountdown}s</strong>.</span>
              </div>
              <button
                onClick={handleStopMonitoring}
                className="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-xs font-bold"
              >
                Dismiss Now
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── 1. Top Mission Control Header ── */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 mb-6 border-b border-[var(--color-sentinel-border-subtle)]">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <span className="px-2.5 py-0.5 rounded-md bg-[var(--color-accent-primary-dim)] border border-[var(--color-accent-primary)]/30 text-[10px] font-bold tracking-wider uppercase text-[var(--color-accent-primary)]">
                SURVEILLANCE MISSION CONTROL
              </span>
              <span className="flex items-center gap-1.5 text-xs text-[var(--color-sentinel-text-dim)]">
                <span className={`w-2 h-2 rounded-full ${isAnyMonitoring ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'}`} />
                {isMonitoring
                  ? `Live Mic Feed (${formatTime(recordingTime)})`
                  : isTelephonyActive
                  ? `SIP Trunk Active (${telephonyCaller})`
                  : 'Engine Standby'}
              </span>
            </div>
            <h1 className="text-2xl lg:text-3xl font-bold tracking-tight text-[var(--color-sentinel-text)] flex items-center gap-3">
              Real-Time Voice Forensics & Threat Interception
            </h1>
          </div>

          {/* Quick Primary Actions */}
          <div className="flex items-center gap-3 shrink-0">
            {isMonitoring ? (
              <button
                onClick={handleStopMonitoring}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-500 hover:bg-red-600 text-white font-bold text-xs shadow-lg shadow-red-500/20 transition-all cursor-pointer"
              >
                <Square className="w-4 h-4 fill-white" /> Stop Sentinel Stream
              </button>
            ) : (
              <button
                onClick={() => handleStartMonitoring()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-accent-primary)] hover:brightness-110 text-[#0c0d14] font-bold text-xs shadow-lg shadow-cyan-500/20 transition-all cursor-pointer"
              >
                <Mic className="w-4 h-4" /> Start Voice Sentinel
              </button>
            )}

            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[var(--color-sentinel-surface)] hover:bg-[var(--color-sentinel-surface-2)] text-[var(--color-sentinel-text)] border border-[var(--color-sentinel-border)] text-xs font-semibold transition-all cursor-pointer"
            >
              <Upload className="w-4 h-4 text-[var(--color-accent-primary)]" /> Upload Audio
            </button>
          </div>
        </div>

        {/* ── 2. Top Glance KPI Cards ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* KPI 1: Active Audio Feed */}
          <div className="p-4 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)]/80 backdrop-blur-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-[var(--color-sentinel-text-dim)] mb-2">
              <span className="font-semibold uppercase tracking-wider text-[10px]">Audio Ingress Channel</span>
              <Radio className={`w-4 h-4 ${isAnyMonitoring ? 'text-emerald-400 animate-pulse' : 'text-gray-500'}`} />
            </div>
            <div>
              <p className="text-base font-bold text-[var(--color-sentinel-text)] truncate">
                {isMonitoring
                  ? (isConnected ? 'Live Microphone Feed' : 'Connecting Audio...')
                  : isTelephonyActive
                  ? `SIP Call (${telephonyCaller})`
                  : 'Idle (Awaiting Stream)'}
              </p>
              <p className="text-[11px] text-[var(--color-sentinel-text-muted)] mt-0.5 font-mono">
                {isAnyMonitoring ? `16kHz · Mono PCM · ${latencyMs}ms` : 'Dial 5000 in Zoiper to stream'}
              </p>
            </div>
          </div>

          {/* KPI 2: Impersonation Threat Score */}
          <div className="p-4 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)]/80 backdrop-blur-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-[var(--color-sentinel-text-dim)] mb-2">
              <span className="font-semibold uppercase tracking-wider text-[10px]">Acoustic Threat Score</span>
              <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${threatBadge.bg} ${threatBadge.text} ${threatBadge.border}`}>
                {threatBadge.label}
              </span>
            </div>
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black font-mono text-[var(--color-sentinel-text)]">
                  {(currentScore * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-[var(--color-sentinel-text-dim)] font-mono">
                  / 100 Risk
                </span>
              </div>
              <p className="text-[11px] text-[var(--color-sentinel-text-muted)] mt-0.5 truncate">
                {activeRiskData?.alert_reason || 'Ensemble AASIST + XLS-R + ECAPA'}
              </p>
            </div>
          </div>

          {/* KPI 3: Voice Biometrics */}
          <div className="p-4 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)]/80 backdrop-blur-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-[var(--color-sentinel-text-dim)] mb-2">
              <span className="font-semibold uppercase tracking-wider text-[10px]">Voice Biometric Match</span>
              <Fingerprint className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <p className="text-base font-bold text-[var(--color-sentinel-text)] truncate">
                {activeRiskData?.profile_name
                  ? activeRiskData.profile_name
                  : (selectedProfileId ? 'Selected Profile' : 'Unenrolled Caller')}
              </p>
              <p className="text-[11px] text-[var(--color-sentinel-text-muted)] mt-0.5 font-mono">
                {speakerMatchScore !== null 
                  ? `${(speakerMatchScore * 100).toFixed(1)}% Similarity (ECAPA)` 
                  : 'Adaptive baseline mode'}
              </p>
            </div>
          </div>

          {/* KPI 4: Financial Context & Intent */}
          <div className="p-4 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)]/80 backdrop-blur-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-[var(--color-sentinel-text-dim)] mb-2">
              <span className="font-semibold uppercase tracking-wider text-[10px]">Financial Interception</span>
              {isExtractedFromSpeech && (
                <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                  AUTO-EXTRACTED
                </span>
              )}
            </div>
            <div>
              <p className="text-base font-bold text-[var(--color-sentinel-text)] truncate">
                ₹{selectedAmount.toLocaleString('en-IN')} · {selectedTransferType}
              </p>
              <p className="text-[11px] text-[var(--color-sentinel-text-muted)] mt-0.5 truncate">
                {selectedLocation}
              </p>
            </div>
          </div>
        </div>

        {/* ── High Risk Alert Banner (conditional) ── */}
        <AnimatePresence>
          {(isHighRisk || countermeasureStatus) && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-6 rounded-2xl border border-red-500/40 bg-red-500/10 p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center shrink-0">
                  <ShieldAlert className="w-5 h-5 text-red-400 animate-pulse" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-red-400 uppercase tracking-wider flex items-center gap-2">
                    High Impersonation Threat Intercepted ({(currentScore * 100).toFixed(0)}%)
                  </h3>
                  <p className="text-xs text-[var(--color-sentinel-text-muted)] mt-0.5 leading-relaxed">
                    {riskData?.alert_reason || 'Synthetic voice signatures or speaker identity mismatch detected. Immediate verification recommended.'}
                  </p>
                  {countermeasureStatus && (
                    <p className="text-xs font-bold text-[var(--color-accent-primary)] mt-1 animate-pulse">
                      ✓ {countermeasureStatus}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 shrink-0">
                <button
                  onClick={() => triggerCountermeasure("Voice Callback Initiated")}
                  className="px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-500/40 text-xs font-bold text-red-300 hover:bg-red-500/30 transition-all cursor-pointer"
                >
                  📞 Initiate Callback
                </button>
                <button
                  onClick={() => triggerCountermeasure("Push MFA Sent to Enrolled Mobile")}
                  className="px-3 py-1.5 rounded-lg bg-[var(--color-accent-primary-dim)] border border-[var(--color-accent-primary)] text-xs font-bold text-[var(--color-accent-primary)] hover:brightness-110 transition-all cursor-pointer"
                >
                  🔐 Push MFA
                </button>
                <button
                  onClick={() => triggerCountermeasure("Escalated to Supervisor Security Desk")}
                  className="px-3 py-1.5 rounded-lg bg-[var(--color-sentinel-surface-3)] border border-[var(--color-sentinel-border)] text-xs font-bold text-[var(--color-sentinel-text)] hover:border-[var(--color-sentinel-text-dim)] transition-all cursor-pointer"
                >
                  ⚠️ Escalate
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── 3. Primary Surveillance Hero Section (Split 7 / 5) ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
          {/* Left (7 cols): Live Audio Spectrum & Waveform Forensics */}
          <div className="lg:col-span-7 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 flex flex-col justify-between shadow-xl">
            <div>
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-[var(--color-sentinel-border-subtle)]">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-[var(--color-accent-primary-dim)] text-[var(--color-accent-primary)]">
                    <Activity className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[var(--color-sentinel-text)]">
                      Live Acoustic Stream Forensics
                    </h3>
                    <p className="text-[10px] text-[var(--color-sentinel-text-dim)]">
                      Dual-domain waveform & frequency spectral breakdown
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-[10px]">
                  <span className="px-2.5 py-1 rounded-md bg-[var(--color-sentinel-surface-2)] text-[var(--color-sentinel-text-muted)] font-mono border border-[var(--color-sentinel-border-subtle)]">
                    16kHz · Mono PCM
                  </span>
                  {isAnyMonitoring && (
                    <span className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      STREAMING
                    </span>
                  )}
                </div>
              </div>

              {/* Waveform & Bars */}
              <div className="space-y-3">
                <div className="rounded-xl overflow-hidden bg-[var(--color-sentinel-surface-2)]/60 border border-[var(--color-sentinel-border-subtle)] p-2">
                  <AudioVisualizer isActive={isAnyMonitoring} variant="waveform" height={130} />
                </div>
                <div className="rounded-xl overflow-hidden bg-[var(--color-sentinel-surface-2)]/60 border border-[var(--color-sentinel-border-subtle)] p-2">
                  <AudioVisualizer isActive={isAnyMonitoring} variant="bars" height={60} />
                </div>
              </div>
            </div>

            {/* Quick Context / Profile Bar at bottom of visualizer */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-4 mt-4 border-t border-[var(--color-sentinel-border-subtle)] text-xs">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-sentinel-text-dim)]">
                  Target Speaker Profile:
                </span>
                <select
                  value={selectedProfileId}
                  onChange={(e) => setSelectedProfileId(e.target.value)}
                  disabled={isMonitoring}
                  className="px-2.5 py-1 rounded-lg bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)] text-xs text-[var(--color-sentinel-text)] font-semibold focus:outline-none cursor-pointer disabled:opacity-60"
                >
                  <option value="">General Monitoring (Unenrolled)</option>
                  {speakerProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} (Enrolled)
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 text-[11px] text-[var(--color-sentinel-text-dim)] font-mono">
                <span>Latency: <strong className="text-cyan-400">{latencyMs}ms</strong></span>
              </div>
            </div>
          </div>

          {/* Right (5 cols): Biometric Threat Gauge & Sub-Score Indicators */}
          <div className="lg:col-span-5 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 flex flex-col justify-between shadow-xl">
            <div>
              <div className="flex items-center justify-between pb-3 mb-2 border-b border-[var(--color-sentinel-border-subtle)]">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-[var(--color-sentinel-text)]">
                    Impersonation Risk Engine
                  </h3>
                </div>
                <span className="text-[9px] text-[var(--color-sentinel-text-dim)] px-2 py-0.5 rounded bg-[var(--color-sentinel-surface-3)] font-mono">
                  EMA α=0.3
                </span>
              </div>

              {/* Gauge */}
              <div className="flex justify-center py-2">
                <RiskGauge score={currentScore} size={190} />
              </div>

              {/* 3 Core Forensic Indicators */}
              <div className="grid grid-cols-3 gap-2 mt-2">
                <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] flex flex-col items-center text-center">
                  <span className="text-[10px] text-[var(--color-sentinel-text-dim)] font-semibold">Deepfake Prob</span>
                  <div className="w-full h-1.5 rounded-full bg-[var(--color-sentinel-surface-3)] overflow-hidden my-1.5">
                    <div className="h-full bg-cyan-400 transition-all duration-500" style={{ width: `${Math.min(deepfakeSubScore * 100, 100)}%` }} />
                  </div>
                  <span className="text-xs font-bold font-mono text-[var(--color-sentinel-text)]">
                    {(deepfakeSubScore * 100).toFixed(0)}%
                  </span>
                </div>

                <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] flex flex-col items-center text-center">
                  <span className="text-[10px] text-[var(--color-sentinel-text-dim)] font-semibold">Voice Match</span>
                  <div className="w-full h-1.5 rounded-full bg-[var(--color-sentinel-surface-3)] overflow-hidden my-1.5">
                    <div className="h-full bg-purple-400 transition-all duration-500" style={{ width: `${Math.min((speakerMatchScore || 0) * 100, 100)}%` }} />
                  </div>
                  <span className="text-xs font-bold font-mono text-[var(--color-sentinel-text)]">
                    {speakerMatchScore !== null ? `${(speakerMatchScore * 100).toFixed(0)}%` : 'N/A'}
                  </span>
                </div>

                <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] flex flex-col items-center text-center">
                  <span className="text-[10px] text-[var(--color-sentinel-text-dim)] font-semibold">Prosody Anomaly</span>
                  <div className="w-full h-1.5 rounded-full bg-[var(--color-sentinel-surface-3)] overflow-hidden my-1.5">
                    <div className="h-full bg-amber-400 transition-all duration-500" style={{ width: `${Math.min(prosodySubScore * 100, 100)}%` }} />
                  </div>
                  <span className="text-xs font-bold font-mono text-[var(--color-sentinel-text)]">
                    {(prosodySubScore * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Context Pill */}
            <div className="pt-3 mt-3 border-t border-[var(--color-sentinel-border-subtle)] flex items-center justify-between text-[11px] text-[var(--color-sentinel-text-dim)]">
              <span>Target: <strong className="text-[var(--color-sentinel-text)]">{selectedPhone}</strong></span>
              <span>Context Weight: <strong className="text-cyan-400">+{Math.round((activeRiskData?.context_risk || 0) * 100)}%</strong></span>
            </div>
          </div>
        </div>

        {/* ── 4. Tabbed Deep Intelligence Workspace ── */}
        <div className="space-y-4">
          {/* Tab Navigation Pill Bar */}
          <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border)] shadow-md overflow-x-auto">
            <button
              onClick={() => setActiveTab('intelligence')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'intelligence'
                  ? 'bg-[var(--color-accent-primary)] text-[#0c0d14] shadow-md'
                  : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Live Speech & Telephony Studio
              {isAnyMonitoring && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              )}
            </button>

            <button
              onClick={() => setActiveTab('forensics')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'forensics'
                  ? 'bg-[var(--color-accent-primary)] text-[#0c0d14] shadow-md'
                  : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              Bio-Acoustic Radar & Ensemble Breakdown
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'history'
                  ? 'bg-[var(--color-accent-primary)] text-[#0c0d14] shadow-md'
                  : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              Session Logs & Security Alerts
              <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-[var(--color-sentinel-surface-3)] text-[var(--color-sentinel-text)]">
                {alerts.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('terminal')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
                activeTab === 'terminal'
                  ? 'bg-[var(--color-accent-primary)] text-[#0c0d14] shadow-md'
                  : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Pipeline Inference Terminal
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
            </button>
          </div>

          {/* Tab Content Panels */}
          <div>
            {/* Tab 1: Live Speech & Telephony Studio */}
            {activeTab === 'intelligence' && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                <LiveCallIntelligenceStudio
                  isMonitoring={isAnyMonitoring}
                  onIntentExtracted={handleLiveIntentExtracted}
                  onCallStart={(geo) => {
                    if (geo?.city && geo?.region) {
                      setSelectedLocation(`${geo.city}, ${geo.region} (${geo.country_code})`);
                    }
                  }}
                  onCallerIdentified={(phone, _name) => {
                    if (phone) setSelectedPhone(phone);
                  }}
                  onTriggerCallMonitoring={() => {
                    handleStartMonitoring();
                  }}
                />
              </motion.div>
            )}

            {/* Tab 2: Bio-Acoustic Radar & Ensemble Breakdown */}
            {activeTab === 'forensics' && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <ForensicAcousticRadar
                  modelDetail={activeRiskData?.model_detail}
                  isMonitoring={isAnyMonitoring}
                />

                <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5">
                  <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)] mb-3">
                    Ensemble Mathematical Model Breakdown
                  </h3>
                  <div className="bg-[var(--color-sentinel-surface-2)] rounded-xl p-4 text-xs font-mono text-[var(--color-sentinel-text-muted)] overflow-x-auto space-y-2">
                    <div>
                      <span className="text-[var(--color-accent-primary)] font-bold">S_ensemble</span> = 
                      {riskData?.has_enrollment 
                        ? ' 0.40×AASIST/XLS-R + 0.35×ECAPA-TDNN (Speaker Verification) + 0.15×Prosody + 0.10×SpeakerDrift'
                        : ' 0.60×AASIST/XLS-R (Deepfake) + 0.30×Prosody (Forensics) + 0.10×SpeakerDrift [Adaptive Re-normalized Mode]'
                      }
                    </div>
                    <div className="text-[var(--color-sentinel-text-dim)] pt-2 border-t border-[var(--color-sentinel-border-subtle)]">
                      {riskData ? (
                        <>AASIST: {riskData.model_detail.aasist_score ?? 'N/A'} | XLS-R: {riskData.model_detail.xlsr_score ?? 'N/A'} | ECAPA Sim: {riskData.model_detail.speaker_similarity !== undefined ? `${(riskData.model_detail.speaker_similarity * 100).toFixed(1)}%` : 'N/A'} | Jitter: {riskData.model_detail.prosody.jitter} | HNR: {riskData.model_detail.prosody.hnr} dB</>
                      ) : (
                        'AASIST (Graph Attention) + XLS-R 300M (Multilingual SSL) + ECAPA-TDNN + Parselmouth Prosody'
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Tab 3: Session Logs & Security Alerts */}
            {activeTab === 'history' && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="grid grid-cols-1 lg:grid-cols-12 gap-5"
              >
                <div className="lg:col-span-8 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 min-h-[360px] max-h-[480px] overflow-y-auto">
                  <SessionsPanel isMonitoring={isMonitoring} sessionId={riskData?.session_id} liveRiskScore={currentScore} sessions={dbSessions} />
                </div>
                <div className="lg:col-span-4 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 min-h-[360px] max-h-[480px] overflow-y-auto">
                  <AlertsPanel alerts={alerts} />
                </div>
              </motion.div>
            )}

            {/* Tab 4: Pipeline Inference Terminal */}
            {activeTab === 'terminal' && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 shadow-xl"
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)] flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-cyan-400" />
                    Live ML Model Inference Stream
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 font-mono">
                    {modelLogs.length} chunks analyzed
                  </span>
                </div>

                <div className="bg-[#141622] rounded-xl p-4 h-80 overflow-y-auto font-mono text-xs text-[#a6accd] flex flex-col gap-2 border border-[#2a2d3d]">
                  {modelLogs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 italic">
                      <Terminal className="w-6 h-6 mb-2 text-gray-600" />
                      Awaiting live audio chunks for real-time model inference...
                    </div>
                  ) : (
                    modelLogs.map((log, idx) => (
                      <div key={`${log.timestamp}-${log.chunk_index}-${idx}`} className="border-b border-[#252839] pb-2 mb-1 last:border-0 last:mb-0 last:pb-0">
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
              </motion.div>
            )}
          </div>
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

      {/* Transaction Interceptor Security Modal */}
      <TransactionInterceptor
        isOpen={isInterceptorOpen}
        onClose={handleCloseInterceptor}
        riskScore={currentScore}
        threatCategory={activeRiskData?.threat_category || 'UNKNOWN'}
        reason={activeRiskData?.alert_reason || 'Voice-risk analysis requires additional speech evidence.'}
        sessionId={activeRiskData?.session_id}
        callerId={activeRiskData?.profile_name ? `${selectedPhone} (${activeRiskData.profile_name})` : (telephonyCaller || selectedPhone)}
        callerPhone={selectedPhone}
      />
    </>
  );
}
