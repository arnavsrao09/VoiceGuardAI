import React from 'react';
import { Radio, ShieldAlert, CheckCircle2 } from 'lucide-react';
import type { ModelDetail } from '../../hooks/useAudioStreamer';

interface ForensicAcousticRadarProps {
  modelDetail?: ModelDetail | null;
  isMonitoring: boolean;
}

export const ForensicAcousticRadar: React.FC<ForensicAcousticRadarProps> = ({
  modelDetail,
  isMonitoring,
}) => {
  const prosody = modelDetail?.prosody;

  // Defaults when idle or stream starting
  const jitter = prosody?.jitter ?? 0.012;
  const shimmer = prosody?.shimmer ?? 0.045;
  const hnr = prosody?.hnr ?? 18.4;
  const spectralFlatness = prosody?.spectral_flatness ?? 0.035;

  // Evaluation criteria against neural vocoder characteristics:
  // Vocoders often exhibit unnaturally low jitter/shimmer or excessive spectral flatness
  const jitterStatus = jitter < 0.003 || jitter > 0.045 ? 'anomaly' : 'normal';
  const shimmerStatus = shimmer < 0.015 || shimmer > 0.12 ? 'anomaly' : 'normal';
  const hnrStatus = hnr < 10.0 || hnr > 32.0 ? 'anomaly' : 'normal';
  const flatnessStatus = spectralFlatness > 0.10 ? 'anomaly' : 'normal';

  const metrics = [
    {
      label: 'Jitter (Pitch Perturbation)',
      value: isMonitoring ? `${(jitter * 100).toFixed(2)}%` : '—',
      raw: jitter,
      normalRange: '0.4% – 3.8%',
      status: isMonitoring ? jitterStatus : 'idle',
      desc: 'Local fundamental frequency micro-perturbation. Zero jitter indicates synthetic vocoder.',
    },
    {
      label: 'Shimmer (Amplitude Var)',
      value: isMonitoring ? `${(shimmer * 100).toFixed(2)}%` : '—',
      raw: shimmer,
      normalRange: '2.0% – 9.5%',
      status: isMonitoring ? shimmerStatus : 'idle',
      desc: 'Cycle-to-cycle amplitude deviation of glottal flow waveforms.',
    },
    {
      label: 'Harmonics-to-Noise (HNR)',
      value: isMonitoring ? `${hnr.toFixed(1)} dB` : '—',
      raw: hnr,
      normalRange: '12.0 – 26.0 dB',
      status: isMonitoring ? hnrStatus : 'idle',
      desc: 'Acoustic glottal harmonics ratio. Abnormal values betray synthetic resynthesis artifacts.',
    },
    {
      label: 'Spectral Flatness (SFM)',
      value: isMonitoring ? spectralFlatness.toFixed(3) : '—',
      raw: spectralFlatness,
      normalRange: '0.01 – 0.08',
      status: isMonitoring ? flatnessStatus : 'idle',
      desc: 'Distribution uniformity of frequency spectrum. Elevated values indicate vocoder noise.',
    },
  ];

  return (
    <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-[var(--color-sentinel-border-subtle)]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-[var(--color-accent-primary-dim)] text-[var(--color-accent-primary)]">
            <Radio className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-[var(--color-sentinel-text)] uppercase tracking-wider flex items-center gap-2">
              Forensic Bio-Acoustic Radar
              {isMonitoring && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              )}
            </h3>
            <p className="text-[11px] text-[var(--color-sentinel-text-dim)]">
              Glottal perturbation, harmonic ratios & vocoder spectral artifact decomposition
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase font-mono px-2.5 py-1 rounded-md bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] text-[var(--color-sentinel-text-dim)]">
            F0 Tracker: {isMonitoring && prosody ? `${Math.round(prosody.f0_mean || 125)} Hz` : '16 kHz Mono'}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {metrics.map((m, idx) => (
          <div
            key={idx}
            className={`p-3.5 rounded-xl border transition-all duration-300 ${
              m.status === 'anomaly'
                ? 'bg-[rgba(239,68,68,0.08)] border-red-500/30'
                : m.status === 'normal'
                ? 'bg-[var(--color-sentinel-surface-2)] border-[var(--color-sentinel-border-subtle)]'
                : 'bg-[var(--color-sentinel-surface-2)] border-[var(--color-sentinel-border-subtle)] opacity-75'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold text-[var(--color-sentinel-text-dim)] uppercase tracking-wide">
                {m.label.split(' ')[0]}
              </span>
              {m.status === 'anomaly' ? (
                <span className="flex items-center gap-1 text-[10px] font-bold text-red-400">
                  <ShieldAlert className="w-3 h-3" /> VOC RES
                </span>
              ) : m.status === 'normal' ? (
                <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400">
                  <CheckCircle2 className="w-3 h-3" /> ORGANIC
                </span>
              ) : (
                <span className="text-[10px] font-mono text-[var(--color-sentinel-text-dim)]">STANDBY</span>
              )}
            </div>

            <div className="flex items-baseline justify-between mb-1.5">
              <span className="text-lg font-mono font-bold text-[var(--color-sentinel-text)] tracking-tight">
                {m.value}
              </span>
              <span className="text-[10px] font-mono text-[var(--color-sentinel-text-dim)]">
                Ref: {m.normalRange}
              </span>
            </div>

            <p className="text-[10px] text-[var(--color-sentinel-text-dim)] leading-tight line-clamp-2">
              {m.desc}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ForensicAcousticRadar;
