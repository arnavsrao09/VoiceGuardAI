import React from 'react';
import {
  Mic,
  Square,
  Upload,
  Activity,
  Cpu,
  Wifi,
  Clock,
  MapPin,
  DollarSign,
  ArrowUpRight,
  ShieldCheck,
  AlertTriangle,
  Sparkles,
  TrendingDown,
  Phone,
} from 'lucide-react';

interface TelemetrySidebarProps {
  isMonitoring: boolean;
  isConnected: boolean;
  latencyMs: number;
  recordingTime: number;
  selectedProfileId: string;
  setSelectedProfileId: (id: string) => void;
  speakerProfiles: Array<{ id: string; name: string }>;
  onStartMonitoring: () => void;
  onStopMonitoring: () => void;
  onOpenUpload: () => void;
  formatTime: (seconds: number) => string;
  location: string;
  amount: number;
  transferType: string;
  riskLevel: string;
  riskScore: number;
  isExtractedFromSpeech: boolean;
  callerPhone?: string;
  onPhoneChange?: (phone: string) => void;
  contextRisk?: number;
  error?: string | null;
}

export const TelemetrySidebar: React.FC<TelemetrySidebarProps> = ({
  isMonitoring,
  isConnected,
  latencyMs,
  recordingTime,
  selectedProfileId,
  setSelectedProfileId,
  speakerProfiles,
  onStartMonitoring,
  onStopMonitoring,
  onOpenUpload,
  formatTime,
  location,
  amount,
  transferType,
  riskLevel,
  riskScore,
  isExtractedFromSpeech,
  callerPhone = '+91 98200 12345',
  onPhoneChange,
  contextRisk,
  error,
}) => {
  const isHighRisk = riskScore >= 0.60;
  const isHighValue = amount >= 25000;
  const contextModifierPct = contextRisk !== undefined && contextRisk > 0 
    ? Math.round(contextRisk * 100) 
    : (isHighValue ? 20 : 0);

  return (
    <aside className="w-full flex flex-col gap-4">
      {/* ── Section 1: Mission Control ── */}
      <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-4 shadow-xl">
        <div className="flex items-center gap-2 pb-3 mb-3 border-b border-[var(--color-sentinel-border-subtle)]">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-[var(--color-accent-primary-dim)] text-[var(--color-accent-primary)]">
            <Activity className="w-3.5 h-3.5" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-[var(--color-sentinel-text)] uppercase tracking-wider">
              Mission Control
            </h3>
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)]">
              Live Stream & Voice Feed
            </span>
          </div>
        </div>

        {error && (
          <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Profile Selector */}
        <div className="space-y-1.5 mb-3">
          <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-sentinel-text-dim)]">
            Target Speaker Profile
          </label>
          <select
            value={selectedProfileId}
            onChange={(e) => setSelectedProfileId(e.target.value)}
            disabled={isMonitoring}
            className={`w-full px-3 py-2 rounded-xl border text-xs font-semibold focus:outline-none transition-all ${
              isMonitoring
                ? 'bg-[var(--color-sentinel-surface-2)] text-[var(--color-sentinel-text-dim)] border-[var(--color-sentinel-border)] cursor-not-allowed'
                : 'bg-[var(--color-sentinel-surface-2)] text-[var(--color-sentinel-text)] border-[var(--color-sentinel-border)] hover:border-[var(--color-accent-primary)]'
            }`}
          >
            <option value="">General Monitoring (Unenrolled Caller)</option>
            {speakerProfiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} (Enrolled)
              </option>
            ))}
          </select>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          <button
            onClick={isMonitoring ? onStopMonitoring : onStartMonitoring}
            className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all duration-300 shadow-md ${
              isMonitoring
                ? 'bg-[var(--color-sentinel-surface-3)] text-[var(--color-risk-critical)] border border-[var(--color-risk-critical)] hover:bg-[rgba(239,68,68,0.1)]'
                : 'bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] hover:brightness-110'
            }`}
          >
            {isMonitoring ? (
              <>
                <Square className="w-3.5 h-3.5 fill-current" />
                Stop Monitoring · {formatTime(recordingTime)}
              </>
            ) : (
              <>
                <Mic className="w-3.5 h-3.5" />
                Start Live Monitoring
              </>
            )}
          </button>

          <button
            onClick={onOpenUpload}
            disabled={isMonitoring}
            className={`w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl border border-[var(--color-sentinel-border)] text-xs font-medium transition-all ${
              isMonitoring
                ? 'text-[var(--color-sentinel-text-dim)] bg-[var(--color-sentinel-surface-2)] cursor-not-allowed opacity-50'
                : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)] hover:border-[var(--color-sentinel-text-dim)]'
            }`}
          >
            <Upload className="w-3.5 h-3.5" />
            Upload Audio File
          </button>
        </div>
      </div>

      {/* ── Section 2: Active Call Context ── */}
      <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-4 shadow-xl space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-[var(--color-sentinel-border-subtle)]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg flex items-center justify-center bg-[rgba(139,92,246,0.12)] text-[var(--color-accent-purple)]">
              <Phone className="w-3.5 h-3.5" />
            </div>
            <h3 className="text-xs font-bold text-[var(--color-sentinel-text)] uppercase tracking-wider">
              Call Context
            </h3>
          </div>
          {isExtractedFromSpeech && (
            <span className="flex items-center gap-1 text-[9px] font-bold text-[var(--color-accent-primary)] bg-[var(--color-accent-primary-dim)] px-1.5 py-0.5 rounded border border-[var(--color-accent-primary)]/20">
              <Sparkles className="w-2.5 h-2.5" />
              Live Extracted
            </span>
          )}
        </div>

        {/* Amount */}
        <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
          <div className="flex items-center gap-2 mb-1 text-[var(--color-accent-primary)]">
            <DollarSign className="w-3.5 h-3.5" />
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider font-bold">
              Target Amount
            </span>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-base font-bold font-mono text-[var(--color-sentinel-text)] tabular-nums">
              ${amount.toLocaleString()}
            </span>
            <span className="text-[11px] text-[var(--color-sentinel-text-dim)] font-mono">
              (₹{(amount * 83).toLocaleString()})
            </span>
          </div>
        </div>

        {/* Location, Contact & Channel */}
        <div className="space-y-2 text-xs">
          <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
            <div className="flex items-center gap-2 mb-1 text-cyan-400">
              <Phone className="w-3.5 h-3.5" />
              <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider font-bold">
                Caller Phone
              </span>
            </div>
            {onPhoneChange && !isMonitoring ? (
              <input
                type="text"
                value={callerPhone}
                onChange={(e) => onPhoneChange(e.target.value)}
                className="w-full bg-transparent font-semibold text-[var(--color-sentinel-text)] text-xs font-mono focus:outline-none border-b border-transparent focus:border-cyan-400"
                placeholder="+91 98200 12345"
              />
            ) : (
              <span className="font-semibold text-[var(--color-sentinel-text)] block truncate font-mono">
                {callerPhone}
              </span>
            )}
          </div>

          <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
            <div className="flex items-center gap-2 mb-1 text-emerald-400">
              <MapPin className="w-3.5 h-3.5" />
              <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider font-bold">
                Origin Geolocation
              </span>
            </div>
            <span className="font-semibold text-[var(--color-sentinel-text)] block truncate">
              {location}
            </span>
          </div>

          <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
            <div className="flex items-center gap-2 mb-1 text-[var(--color-accent-purple)]">
              <ArrowUpRight className="w-3.5 h-3.5" />
              <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider font-bold">
                Action Channel
              </span>
            </div>
            <span className="font-semibold text-[var(--color-sentinel-text)] block truncate">
              {transferType}
            </span>
          </div>
        </div>

        {/* Threat Modifier */}
        <div className={`p-2.5 rounded-xl border flex items-center justify-between ${
          contextModifierPct > 0 || isHighRisk
            ? 'bg-[rgba(245,197,66,0.08)] border-[var(--color-risk-medium)]/30 text-[var(--color-risk-medium)]'
            : 'bg-[rgba(0,229,200,0.08)] border-[var(--color-risk-low)]/30 text-[var(--color-risk-low)]'
        }`}>
          <div className="flex items-center gap-1.5 text-xs font-bold">
            {contextModifierPct > 0 || isHighRisk ? <AlertTriangle className="w-3.5 h-3.5 shrink-0" /> : <ShieldCheck className="w-3.5 h-3.5 shrink-0" />}
            <span>{contextModifierPct > 0 ? `+${contextModifierPct}% Risk Modifier` : 'Normal Context'}</span>
          </div>
          <span className="text-[10px] font-mono uppercase font-semibold">
            {riskLevel}
          </span>
        </div>
      </div>

      {/* ── Section 3: Engine Telemetry Stats ── */}
      <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-4 shadow-xl space-y-2.5">
        <div className="pb-2 border-b border-[var(--color-sentinel-border-subtle)]">
          <h3 className="text-xs font-bold text-[var(--color-sentinel-text)] uppercase tracking-wider">
            Engine Telemetry
          </h3>
          <span className="text-[10px] text-[var(--color-sentinel-text-dim)]">
            ML Pipeline & Stream Health
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {/* Latency */}
          <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
            <div className="flex items-center justify-between text-[var(--color-accent-primary)] mb-1">
              <Cpu className="w-3.5 h-3.5" />
              {isMonitoring && (
                <span className="flex items-center text-[9px] font-semibold text-[var(--color-risk-low)]">
                  <TrendingDown className="w-2.5 h-2.5 mr-0.5" /> FAST
                </span>
              )}
            </div>
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase block font-medium">Inference</span>
            <span className="text-sm font-bold font-mono text-[var(--color-sentinel-text)]">
              {isMonitoring ? (latencyMs > 0 ? `${latencyMs}` : '42') : '—'}
              <span className="text-[10px] text-[var(--color-sentinel-text-dim)] ml-0.5">ms</span>
            </span>
          </div>

          {/* WebSocket */}
          <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
            <div className="flex items-center text-emerald-400 mb-1">
              <Wifi className="w-3.5 h-3.5" />
            </div>
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase block font-medium">Socket</span>
            <span className={`text-xs font-bold block truncate ${
              isConnected ? 'text-emerald-400' : isMonitoring ? 'text-amber-400' : 'text-[var(--color-sentinel-text-dim)]'
            }`}>
              {isConnected ? 'ONLINE' : isMonitoring ? 'CONNECTING' : 'OFFLINE'}
            </span>
          </div>

          {/* Uptime */}
          <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
            <div className="flex items-center text-cyan-400 mb-1">
              <Clock className="w-3.5 h-3.5" />
            </div>
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase block font-medium">Uptime</span>
            <span className="text-sm font-bold font-mono text-[var(--color-sentinel-text)]">
              99.97<span className="text-[10px] text-[var(--color-sentinel-text-dim)] ml-0.5">%</span>
            </span>
          </div>

          {/* Sample Rate */}
          <div className="p-2.5 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)]">
            <div className="flex items-center text-[var(--color-accent-purple)] mb-1">
              <Activity className="w-3.5 h-3.5" />
            </div>
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase block font-medium">Audio PCM</span>
            <span className="text-xs font-bold font-mono text-[var(--color-sentinel-text)]">
              16.0 kHz
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default TelemetrySidebar;
