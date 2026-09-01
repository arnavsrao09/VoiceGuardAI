import { useRef, useEffect, useCallback } from 'react';

interface AudioVisualizerProps {
  isActive?: boolean;
  variant?: 'waveform' | 'bars';
  height?: number;
  color?: string;
}

export default function AudioVisualizer({
  isActive = true,
  variant = 'waveform',
  height = 120,
  color = 'var(--color-accent-primary)',
}: AudioVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const timeRef = useRef(0);

  const drawWaveform = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number, t: number) => {
      ctx.clearRect(0, 0, w, h);

      // Draw grid lines
      ctx.strokeStyle = 'rgba(42, 43, 58, 0.5)';
      ctx.lineWidth = 0.5;
      for (let y = 0; y < h; y += h / 6) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      const mid = h / 2;
      const layers = [
        { amp: isActive ? 0.35 : 0.05, freq: 0.02, speed: 1.2, alpha: 0.6 },
        { amp: isActive ? 0.25 : 0.03, freq: 0.035, speed: 0.8, alpha: 0.35 },
        { amp: isActive ? 0.15 : 0.02, freq: 0.05, speed: 1.5, alpha: 0.2 },
      ];

      layers.forEach(({ amp, freq, speed, alpha }) => {
        ctx.beginPath();
        ctx.moveTo(0, mid);

        for (let x = 0; x < w; x++) {
          const noise = isActive
            ? Math.sin(x * 0.1 + t * 3) * 3 + Math.sin(x * 0.23 + t * 2.7) * 2
            : 0;
          const y =
            mid +
            Math.sin(x * freq + t * speed) * (mid * amp) +
            Math.sin(x * freq * 2.3 + t * speed * 1.7) * (mid * amp * 0.4) +
            noise;
          ctx.lineTo(x, y);
        }

        ctx.strokeStyle = color.startsWith('var(')
          ? `rgba(0, 229, 200, ${alpha})`
          : color;
        ctx.lineWidth = 1.8;
        ctx.stroke();

        // Fill below
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, mid - h * amp, 0, h);
        grad.addColorStop(0, `rgba(0, 229, 200, ${alpha * 0.15})`);
        grad.addColorStop(1, 'rgba(0, 229, 200, 0)');
        ctx.fillStyle = grad;
        ctx.fill();
      });
    },
    [isActive, color]
  );

  const drawBars = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number, t: number) => {
      ctx.clearRect(0, 0, w, h);
      const barCount = 48;
      const gap = 3;
      const barW = (w - gap * (barCount - 1)) / barCount;

      for (let i = 0; i < barCount; i++) {
        const base = isActive
          ? Math.abs(Math.sin(i * 0.25 + t * 1.5)) * 0.7 +
            Math.abs(Math.sin(i * 0.4 + t * 2.2)) * 0.3
          : 0.05 + Math.sin(i * 0.3 + t * 0.5) * 0.03;

        const barH = Math.max(4, base * h * 0.85);
        const x = i * (barW + gap);
        const y = h - barH;

        const grad = ctx.createLinearGradient(x, y, x, h);
        grad.addColorStop(0, `rgba(0, 229, 200, ${isActive ? 0.9 : 0.3})`);
        grad.addColorStop(0.5, `rgba(139, 92, 246, ${isActive ? 0.6 : 0.15})`);
        grad.addColorStop(1, 'rgba(139, 92, 246, 0.05)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, barW, barH, 2);
        ctx.fill();
      }
    },
    [isActive]
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    const drawFn = variant === 'bars' ? drawBars : drawWaveform;

    const animate = () => {
      timeRef.current += 0.016;
      const rect = canvas.getBoundingClientRect();
      ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
      drawFn(ctx, rect.width, rect.height, timeRef.current);
      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [variant, drawWaveform, drawBars]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full rounded-lg"
      style={{ height }}
    />
  );
}
