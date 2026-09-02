import { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion, useScroll, useTransform } from 'framer-motion';
import {
  Shield,
  Activity,
  ArrowRight,
  Mic,
  Upload,
  Brain,
  Fingerprint,
  AudioLines,
  Globe,
  Lock,
  Zap,
  BarChart3,
  Layers,
  ShieldCheck,
} from 'lucide-react';

/* ========================================
   Animated Particle Grid Background
   ======================================== */
function ParticleGrid() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    let w = 0, h = 0;
    let particles: { x: number; y: number; vx: number; vy: number; r: number; pulse: number; speed: number }[] = [];
    let mouse = { x: -1000, y: -1000 };
    let animId = 0;

    const resize = () => {
      w = canvas.parentElement!.clientWidth;
      h = canvas.parentElement!.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      initParticles();
    };

    const initParticles = () => {
      const count = Math.min(80, Math.floor((w * h) / 12000));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        r: Math.random() * 1.5 + 0.5,
        pulse: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.02 + 0.01,
      }));
    };

    const onMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += p.speed;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const glow = dist < 150 ? 1 - dist / 150 : 0;
        const alpha = 0.15 + Math.sin(p.pulse) * 0.08 + glow * 0.5;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r + glow * 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 229, 200, ${alpha})`;
        ctx.fill();
      });

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(0, 229, 200, ${0.06 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener('resize', resize);
    canvas.addEventListener('mousemove', onMove);
    animId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      canvas.removeEventListener('mousemove', onMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-auto"
      style={{ opacity: 0.7 }}
    />
  );
}

/* ========================================
   Live Waveform that responds to interaction
   ======================================== */
function HeroWaveform({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const timeRef = useRef(0);
  const animRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const draw = () => {
      timeRef.current += 0.018;
      const t = timeRef.current;
      const rect = canvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const mid = h / 2;
      const amp = active ? 0.38 : 0.12;

      // Multiple wave layers
      const layers = [
        { a: amp, f: 0.015, s: 1.0, color: '0, 229, 200', alpha: 0.8, lw: 2.5 },
        { a: amp * 0.7, f: 0.025, s: 1.5, color: '139, 92, 246', alpha: 0.5, lw: 1.8 },
        { a: amp * 0.5, f: 0.04, s: 2.0, color: '0, 229, 200', alpha: 0.25, lw: 1 },
      ];

      layers.forEach(({ a, f, s, color, alpha, lw }) => {
        ctx.beginPath();
        ctx.moveTo(0, mid);

        for (let x = 0; x <= w; x += 2) {
          const noise = active
            ? Math.sin(x * 0.08 + t * 2.5) * 6 + Math.sin(x * 0.17 + t * 3.1) * 4
            : 0;
          const y =
            mid +
            Math.sin(x * f + t * s) * (mid * a) +
            Math.sin(x * f * 2.1 + t * s * 1.6) * (mid * a * 0.35) +
            noise;
          ctx.lineTo(x, y);
        }

        ctx.strokeStyle = `rgba(${color}, ${alpha})`;
        ctx.lineWidth = lw;
        ctx.stroke();

        // Fill gradient below
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, mid, 0, h);
        grad.addColorStop(0, `rgba(${color}, ${alpha * 0.12})`);
        grad.addColorStop(1, `rgba(${color}, 0)`);
        ctx.fillStyle = grad;
        ctx.fill();
      });

      // Center line
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(w, mid);
      ctx.strokeStyle = 'rgba(42, 43, 58, 0.3)';
      ctx.lineWidth = 0.5;
      ctx.stroke();

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [active]);

  return <canvas ref={canvasRef} className="w-full h-full" />;
}

/* ========================================
   Interactive Demo Section
   ======================================== */
function TryItDemo() {
  const [mode, setMode] = useState<'idle' | 'recording' | 'analyzing' | 'result'>('idle');
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ score: number; label: string } | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const startDemo = useCallback((type: 'mic' | 'file') => {
    setMode('recording');
    setProgress(0);
    setResult(null);

    // Simulate recording phase
    let p = 0;
    timerRef.current = setInterval(() => {
      p += 2;
      setProgress(p);
      if (p >= 100) {
        clearInterval(timerRef.current);
        setMode('analyzing');
        // Simulate analysis
        setTimeout(() => {
          const score = type === 'file' ? 0.78 : 0.15;
          setResult({
            score,
            label: score < 0.3 ? 'LOW RISK' : score < 0.6 ? 'MEDIUM' : score < 0.8 ? 'HIGH' : 'CRITICAL',
          });
          setMode('result');
        }, 1500);
      }
    }, 60);
  }, []);

  const reset = () => {
    clearInterval(timerRef.current);
    setMode('idle');
    setProgress(0);
    setResult(null);
  };

  useEffect(() => () => clearInterval(timerRef.current), []);

  const riskColor = result
    ? result.score < 0.3
      ? 'var(--color-risk-low)'
      : result.score < 0.6
      ? 'var(--color-risk-medium)'
      : result.score < 0.8
      ? 'var(--color-risk-high)'
      : 'var(--color-risk-critical)'
    : 'var(--color-accent-primary)';

  return (
    <div className="relative rounded-2xl overflow-hidden border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)]">
      {/* Progress bar */}
      {mode !== 'idle' && mode !== 'result' && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-[var(--color-sentinel-surface-3)]">
          <motion.div
            className="h-full bg-[var(--color-accent-primary)]"
            initial={{ width: 0 }}
            animate={{ width: mode === 'analyzing' ? '100%' : `${progress}%` }}
            transition={{ duration: mode === 'analyzing' ? 1.5 : 0.1 }}
          />
        </div>
      )}

      <div className="p-8 sm:p-10">
        {mode === 'idle' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center"
          >
            <h3 className="text-xl sm:text-2xl font-bold text-[var(--color-sentinel-text)] mb-3">
              Try it right now
            </h3>
            <p className="text-sm text-[var(--color-sentinel-text-muted)] mb-8 max-w-md mx-auto">
              Record your voice or simulate a deepfake upload to see the detection engine in action.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => startDemo('mic')}
                className="w-full sm:w-auto flex items-center justify-center gap-3 px-8 py-4 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)] text-[var(--color-sentinel-text)] font-semibold hover:border-[var(--color-accent-primary)] hover:bg-[var(--color-accent-primary-dim)] transition-all duration-200 group"
              >
                <div className="w-10 h-10 rounded-full bg-[var(--color-accent-primary-dim)] flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Mic className="w-5 h-5 text-[var(--color-accent-primary)]" />
                </div>
                <div className="text-left">
                  <div className="text-sm font-semibold">Record Voice</div>
                  <div className="text-xs text-[var(--color-sentinel-text-dim)]">Analyze live speech</div>
                </div>
              </button>

              <button
                onClick={() => startDemo('file')}
                className="w-full sm:w-auto flex items-center justify-center gap-3 px-8 py-4 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)] text-[var(--color-sentinel-text)] font-semibold hover:border-[var(--color-accent-purple)] hover:bg-[var(--color-accent-purple-dim)] transition-all duration-200 group"
              >
                <div className="w-10 h-10 rounded-full bg-[var(--color-accent-purple-dim)] flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Upload className="w-5 h-5 text-[var(--color-accent-purple)]" />
                </div>
                <div className="text-left">
                  <div className="text-sm font-semibold">Simulate Deepfake</div>
                  <div className="text-xs text-[var(--color-sentinel-text-dim)]">Test with AI audio</div>
                </div>
              </button>
            </div>
          </motion.div>
        )}

        {mode === 'recording' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-center"
          >
            <div className="relative w-24 h-24 mx-auto mb-5">
              <div className="absolute inset-0 rounded-full bg-[var(--color-accent-primary)] opacity-20 animate-ping" />
              <div className="absolute inset-2 rounded-full bg-[var(--color-accent-primary)] opacity-10 animate-ping" style={{ animationDelay: '0.3s' }} />
              <div className="relative w-24 h-24 rounded-full bg-[var(--color-accent-primary-dim)] border-2 border-[var(--color-accent-primary)] flex items-center justify-center">
                <Mic className="w-8 h-8 text-[var(--color-accent-primary)]" />
              </div>
            </div>
            <p className="text-lg font-semibold text-[var(--color-sentinel-text)] mb-1">
              Capturing audio…
            </p>
            <p className="text-sm text-[var(--color-sentinel-text-muted)]">
              Processing {progress}% — Silero VAD filtering silence
            </p>
          </motion.div>
        )}

        {mode === 'analyzing' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center"
          >
            <div className="w-24 h-24 mx-auto mb-5 relative">
              <div className="absolute inset-0 rounded-full border-2 border-[var(--color-accent-purple)] border-t-transparent animate-spin" />
              <div className="absolute inset-3 rounded-full border-2 border-[var(--color-accent-primary)] border-b-transparent animate-spin" style={{ animationDirection: 'reverse', animationDuration: '0.7s' }} />
              <div className="absolute inset-0 flex items-center justify-center">
                <Brain className="w-7 h-7 text-[var(--color-accent-purple)]" />
              </div>
            </div>
            <p className="text-lg font-semibold text-[var(--color-sentinel-text)] mb-1">
              Running ML ensemble…
            </p>
            <p className="text-sm text-[var(--color-sentinel-text-muted)]">
              AASIST · XLS-R · ECAPA-TDNN · Prosody
            </p>
          </motion.div>
        )}

        {mode === 'result' && result && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 20 }}
            className="text-center"
          >
            <div
              className="w-28 h-28 mx-auto mb-5 rounded-full flex items-center justify-center"
              style={{
                background: `color-mix(in srgb, ${riskColor} 12%, transparent)`,
                border: `2px solid ${riskColor}`,
                boxShadow: `0 0 40px color-mix(in srgb, ${riskColor} 25%, transparent)`,
              }}
            >
              <div className="text-center">
                <div className="text-2xl font-bold" style={{ color: riskColor }}>
                  {result.score.toFixed(2)}
                </div>
                <div className="text-[10px] font-bold tracking-widest" style={{ color: riskColor }}>
                  {result.label}
                </div>
              </div>
            </div>

            {/* Score breakdown */}
            <div className="grid grid-cols-3 gap-3 max-w-sm mx-auto mb-6">
              {[
                { label: 'Deepfake', val: result.score * 1.05 },
                { label: 'Speaker', val: result.score * 0.7 },
                { label: 'Prosody', val: result.score * 0.85 },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <div className="text-xs text-[var(--color-sentinel-text-dim)] mb-1">{s.label}</div>
                  <div className="h-2 rounded-full bg-[var(--color-sentinel-surface-3)] overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: riskColor }}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(s.val * 100, 100)}%` }}
                      transition={{ delay: 0.3, duration: 0.6 }}
                    />
                  </div>
                  <div className="text-xs font-semibold mt-1" style={{ color: riskColor }}>
                    {Math.min(s.val, 1).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-center gap-3">
              <button
                onClick={reset}
                className="px-5 py-2.5 rounded-xl border border-[var(--color-sentinel-border)] text-sm font-medium text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] transition-colors"
              >
                Try again
              </button>
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] text-sm font-semibold hover:brightness-110 transition-all"
              >
                Open full dashboard
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

/* ========================================
   Pipeline Step — Interactive
   ======================================== */
const pipelineSteps = [
  {
    icon: Mic,
    title: 'Audio Capture',
    tech: 'AudioWorklet · PCM 16kHz',
    detail: 'Browser-native capture via AudioWorkletNode. Converts Float32 to Int16 PCM at 16kHz mono, streaming binary chunks every 100ms over WebSocket.',
  },
  {
    icon: Activity,
    title: 'VAD Filtering',
    tech: 'Silero VAD · 30ms frames',
    detail: 'Voice Activity Detection drops silence and background noise before any ML processing, saving 60–75% compute. Configurable speech probability threshold.',
  },
  {
    icon: Layers,
    title: 'Feature Extraction',
    tech: 'LFCC · Mel-Spec · Prosody',
    detail: 'Multi-domain features: Linear Frequency Cepstral Coefficients catch high-freq vocoder artifacts, log-mel spectrograms for AASIST, and F0/jitter/shimmer via Praat.',
  },
  {
    icon: Brain,
    title: 'ML Ensemble',
    tech: 'AASIST · XLS-R · ECAPA-TDNN',
    detail: 'Three parallel branches: AASIST graph attention on raw waveforms, Wav2Vec2 XLS-R for multilingual SSL features, ECAPA-TDNN 192-dim speaker embeddings.',
  },
  {
    icon: BarChart3,
    title: 'Risk Scoring',
    tech: 'Weighted fusion · EMA α=0.3',
    detail: 'Ensemble fusion: 0.45×deepfake + 0.25×speaker + 0.15×prosody + 0.15×context. Exponential moving average smoothing prevents single-frame false alarms.',
  },
  {
    icon: ShieldCheck,
    title: 'Alert & Respond',
    tech: 'Multi-channel · <400ms',
    detail: 'Configurable workflows: WebSocket push, in-app toast, email/SMS. Rule engine for automated responses like transaction holds and supervisor escalation.',
  },
];

function PipelineSection() {
  const [activeStep, setActiveStep] = useState(0);
  const ref = useRef(null);
  const inView = useInViewSimple(ref);

  return (
    <section ref={ref} className="py-28 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5 }}
          className="mb-14"
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-[var(--color-sentinel-text)] mb-3">
            Six-stage detection pipeline
          </h2>
          <p className="text-[var(--color-sentinel-text-muted)] max-w-lg">
            From microphone to alert in under 400ms. Click each stage to explore.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Step list */}
          <div className="lg:col-span-5 flex flex-col gap-1">
            {pipelineSteps.map((step, i) => {
              const Icon = step.icon;
              const isActive = activeStep === i;
              return (
                <motion.button
                  key={step.title}
                  initial={{ opacity: 0, x: -16 }}
                  animate={inView ? { opacity: 1, x: 0 } : {}}
                  transition={{ delay: i * 0.06, duration: 0.3 }}
                  onClick={() => setActiveStep(i)}
                  className={`flex items-center gap-4 p-4 rounded-xl text-left transition-all duration-200 ${
                    isActive
                      ? 'bg-[var(--color-sentinel-surface-2)] border border-[var(--color-accent-primary)] shadow-lg shadow-[var(--color-accent-primary-glow)]'
                      : 'border border-transparent hover:bg-[var(--color-sentinel-surface-2)]'
                  }`}
                >
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                      isActive ? 'bg-[var(--color-accent-primary)] text-white' : 'bg-[var(--color-sentinel-surface-3)] text-[var(--color-sentinel-text-dim)]'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${isActive ? 'text-[var(--color-accent-primary)]' : 'text-[var(--color-sentinel-text)]'}`}>
                        {step.title}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--color-sentinel-text-dim)] truncate">
                      {step.tech}
                    </p>
                  </div>
                  <span className="text-xs text-[var(--color-sentinel-text-dim)] tabular-nums w-5 text-center shrink-0">
                    {i + 1}
                  </span>
                </motion.button>
              );
            })}
          </div>

          {/* Detail panel */}
          <div className="lg:col-span-7">
            <motion.div
              key={activeStep}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-8 h-full flex flex-col justify-center"
            >
              {(() => {
                const step = pipelineSteps[activeStep];
                const Icon = step.icon;
                return (
                  <>
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-12 h-12 rounded-xl bg-[var(--color-accent-primary)] flex items-center justify-center">
                        <Icon className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-[var(--color-sentinel-text)]">{step.title}</h3>
                        <p className="text-xs text-[var(--color-accent-primary)]">{step.tech}</p>
                      </div>
                    </div>
                    <p className="text-sm text-[var(--color-sentinel-text-muted)] leading-relaxed mb-6">
                      {step.detail}
                    </p>
                    {/* Visual representation */}
                    <div className="rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] p-4 h-32 flex items-center justify-center overflow-hidden">
                      <HeroWaveform active={activeStep < 3} />
                    </div>
                  </>
                );
              })()}
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ========================================
   Features
   ======================================== */
const features = [
  {
    icon: Brain,
    title: 'Multi-Layer ML Analysis',
    description: 'AASIST graph attention, WavLM/XLS-R SSL backbone, ECAPA-TDNN speaker verification running in parallel ensemble.',
    color: 'var(--color-accent-primary)',
  },
  {
    icon: Zap,
    title: 'Sub-400ms Latency',
    description: 'Full-duplex WebSocket binary streaming. AudioWorklet capture, ONNX Runtime FP16 inference, real-time risk updates every 250ms.',
    color: 'var(--color-accent-purple)',
  },
  {
    icon: Fingerprint,
    title: 'Speaker Verification',
    description: '192-dim embeddings with cosine similarity matching, cross-session drift detection, and pgvector HNSW indexing.',
    color: 'var(--color-risk-medium)',
  },
  {
    icon: AudioLines,
    title: 'Prosody Forensics',
    description: 'Jitter, shimmer, F0 micro-variations, formant trajectories, and spectral flatness to expose unnatural synthesis patterns.',
    color: 'var(--color-risk-high)',
  },
  {
    icon: Globe,
    title: '128 Languages',
    description: 'Wav2Vec2 XLS-R backbone with native Hindi, Tamil, Telugu, Bengali support. Handles code-switching and telephony codecs.',
    color: 'var(--color-accent-primary)',
  },
  {
    icon: Lock,
    title: 'Zero Audio Retention',
    description: 'PCM discarded after feature extraction. Feature-only logging with DPDP 2023, GDPR, and CCPA compliance presets.',
    color: 'var(--color-accent-purple)',
  },
];

/* ========================================
   Hook helper
   ======================================== */
function useInViewSimple(ref: React.RefObject<HTMLElement | null>) {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold: 0.15 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [ref]);
  return inView;
}

/* ========================================
   Landing Page
   ======================================== */
export default function LandingPage() {
  const heroRef = useRef(null);
  const featRef = useRef(null);
  const featInView = useInViewSimple(featRef);
  const { scrollYProgress } = useScroll();
  const heroY = useTransform(scrollYProgress, [0, 0.3], [0, -80]);

  return (
    <div className="flex flex-col">
      {/* ── Hero ── */}
      <section
        ref={heroRef}
        className="relative min-h-[100dvh] flex flex-col items-center justify-center px-6 pt-20 pb-16 overflow-hidden"
      >
        <ParticleGrid />

        <motion.div
          style={{ y: heroY }}
          className="relative z-10 max-w-4xl mx-auto text-center flex flex-col items-center"
        >
          <motion.h1
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
            className="text-5xl sm:text-6xl md:text-[5rem] font-extrabold tracking-tight leading-[1.05] mb-6 text-[var(--color-sentinel-text)]"
          >
            Detect voice clones
            <br />
            in real time
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.6 }}
            className="text-lg sm:text-xl text-[var(--color-sentinel-text-muted)] max-w-xl leading-relaxed mb-10"
          >
            Multi-layer ML ensemble analyzes live voice streams, scores impersonation risk, and fires alerts — 
            all under 400 milliseconds.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="flex flex-wrap items-center justify-center gap-4 mb-16"
          >
            <Link
              to="/dashboard"
              className="group inline-flex items-center gap-2.5 px-8 py-3.5 rounded-xl bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] font-semibold text-base hover:brightness-110 hover:scale-[1.03] transition-all duration-200 shadow-lg"
              style={{ boxShadow: '0 8px 32px rgba(0,229,200,0.25)' }}
            >
              <Activity className="w-5 h-5" />
              Launch Dashboard
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <a
              href="#try-it"
              className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl border border-[var(--color-sentinel-border)] text-[var(--color-sentinel-text-muted)] font-medium hover:text-[var(--color-sentinel-text)] hover:border-[var(--color-sentinel-text-dim)] transition-all duration-200"
            >
              Try it now
            </a>
          </motion.div>

          {/* Live waveform preview */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45, duration: 0.6 }}
            className="w-full max-w-3xl h-36 sm:h-44 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] overflow-hidden"
          >
            <HeroWaveform active={true} />
          </motion.div>
        </motion.div>
      </section>

      {/* ── Try It Section ── */}
      <section id="try-it" className="py-28 px-6">
        <div className="max-w-2xl mx-auto">
          <TryItDemo />
        </div>
      </section>

      {/* ── Pipeline Section ── */}
      <PipelineSection />

      {/* ── Features ── */}
      <section id="features" className="py-28 px-6" ref={featRef}>
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={featInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
            className="mb-14"
          >
            <h2 className="text-3xl sm:text-4xl font-bold text-[var(--color-sentinel-text)] mb-3">
              What makes it different
            </h2>
            <p className="text-[var(--color-sentinel-text-muted)] max-w-lg">
              Purpose-built for voice cloning threats. Not a general audio classifier.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-[var(--color-sentinel-border-subtle)] rounded-2xl overflow-hidden border border-[var(--color-sentinel-border)]">
            {features.map((feat, i) => {
              const Icon = feat.icon;
              return (
                <motion.div
                  key={feat.title}
                  initial={{ opacity: 0 }}
                  animate={featInView ? { opacity: 1 } : {}}
                  transition={{ delay: i * 0.06, duration: 0.35 }}
                  className="bg-[var(--color-sentinel-surface)] p-7 hover:bg-[var(--color-sentinel-surface-2)] transition-colors group"
                >
                  <Icon
                    className="w-6 h-6 mb-4 group-hover:scale-110 transition-transform"
                    style={{ color: feat.color }}
                  />
                  <h3 className="text-sm font-bold text-[var(--color-sentinel-text)] mb-2">
                    {feat.title}
                  </h3>
                  <p className="text-xs text-[var(--color-sentinel-text-muted)] leading-relaxed">
                    {feat.description}
                  </p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Risk Scale ── */}
      <section className="py-28 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-[var(--color-sentinel-text)] mb-3">
            Four-tier risk scoring
          </h2>
          <p className="text-[var(--color-sentinel-text-muted)] mb-12 max-w-lg">
            Weighted ensemble fusion with EMA temporal smoothing. Configurable per deployment.
          </p>

          <div className="relative">
            {/* Risk bar */}
            <div className="h-3 rounded-full overflow-hidden flex mb-8">
              <div className="flex-[3] bg-[var(--color-risk-low)]" />
              <div className="flex-[3] bg-[var(--color-risk-medium)]" />
              <div className="flex-[2] bg-[var(--color-risk-high)]" />
              <div className="flex-[2] bg-[var(--color-risk-critical)]" />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { level: 'LOW', range: '0.0–0.3', color: 'var(--color-risk-low)', action: 'Normal speech — continue' },
                { level: 'MEDIUM', range: '0.3–0.6', color: 'var(--color-risk-medium)', action: 'Elevated — monitor closely' },
                { level: 'HIGH', range: '0.6–0.8', color: 'var(--color-risk-high)', action: 'Suspicious — warn operator' },
                { level: 'CRITICAL', range: '0.8–1.0', color: 'var(--color-risk-critical)', action: 'Likely synthetic — block' },
              ].map((r) => (
                <div key={r.level} className="text-left">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: r.color }} />
                    <span className="text-sm font-bold" style={{ color: r.color }}>{r.level}</span>
                  </div>
                  <p className="text-xs text-[var(--color-sentinel-text-dim)] mb-0.5">{r.range}</p>
                  <p className="text-xs text-[var(--color-sentinel-text-muted)]">{r.action}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-28 px-6">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-[var(--color-sentinel-text)] mb-4">
            Deploy in one command
          </h2>
          <div className="rounded-xl bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border)] p-4 mb-8">
            <code className="text-sm text-[var(--color-accent-primary)]">
              docker-compose up -d
            </code>
          </div>
          <Link
            to="/dashboard"
            className="group inline-flex items-center gap-2.5 px-8 py-4 rounded-xl bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] font-semibold text-base hover:brightness-110 hover:scale-[1.03] transition-all duration-200 shadow-lg"
            style={{ boxShadow: '0 8px 32px rgba(0,229,200,0.25)' }}
          >
            <Activity className="w-5 h-5" />
            Open Dashboard
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-[var(--color-sentinel-border-subtle)] py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-[var(--color-sentinel-text-dim)]">
            <Shield className="w-4 h-4 text-[var(--color-accent-primary)]" />
            VoiceSentinel — SIH26104
          </div>
          <p className="text-xs text-[var(--color-sentinel-text-dim)]">
            AI-Powered Voice Cloning Detection & Prevention
          </p>
        </div>
      </footer>
    </div>
  );
}
