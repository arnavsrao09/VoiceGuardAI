import { useState } from 'react';
import { Settings, Sliders, Cpu, Save, RefreshCw } from 'lucide-react';

export default function SettingsPage() {
  const [vadThreshold, setVadThreshold] = useState(0.5);
  const [deepfakeThreshold, setDeepfakeThreshold] = useState(0.6);
  const [speakerThreshold, setSpeakerThreshold] = useState(0.75);

  const [wDeepfake, setWDeepfake] = useState(0.40);
  const [wSpeaker, setWSpeaker] = useState(0.25);
  const [wProsody, setWProsody] = useState(0.15);
  const [wDrift, setWDrift] = useState(0.10);

  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
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
              <label className="text-xs font-semibold text-[var(--color-sentinel-text-muted)] mb-1 block">Speaker Identity Drift Weight ({wDrift.toFixed(2)})</label>
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
      </div>
    </div>
  );
}
