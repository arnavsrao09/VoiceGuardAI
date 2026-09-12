import React from 'react';
import { motion } from 'framer-motion';
import { MapPin, DollarSign, ArrowUpRight, ShieldCheck, AlertTriangle, Sparkles } from 'lucide-react';

interface ContextRibbonProps {
  location: string;
  amount: number;
  transferType: string;
  riskLevel: string;
  riskScore: number;
  isExtractedFromSpeech: boolean;
}

export const ContextRibbon: React.FC<ContextRibbonProps> = ({
  location,
  amount,
  transferType,
  riskLevel,
  riskScore,
  isExtractedFromSpeech,
}) => {
  const isHighRisk = riskScore >= 0.60;
  const isHighValue = amount >= 25000;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-5"
    >
      {/* 1. Caller Origin & Telemetry */}
      <div className="flex items-center gap-3 p-3.5 rounded-xl bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border-subtle)] transition-all">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-[rgba(16,185,129,0.12)] text-emerald-400">
          <MapPin className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider block font-medium">
            Caller Geolocation
          </span>
          <span className="text-xs font-semibold text-[var(--color-sentinel-text)] truncate block">
            {location}
          </span>
        </div>
      </div>

      {/* 2. Target Transaction Amount */}
      <div className="flex items-center gap-3 p-3.5 rounded-xl bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border-subtle)] transition-all">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-[var(--color-accent-primary-dim)] text-[var(--color-accent-primary)]">
          <DollarSign className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider font-medium">
              Target Amount
            </span>
            {isExtractedFromSpeech && (
              <span className="flex items-center gap-1 text-[9px] font-bold text-[var(--color-accent-primary)] bg-[var(--color-accent-primary-dim)] px-1.5 py-0.2 rounded border border-[var(--color-accent-primary)]/20">
                <Sparkles className="w-2.5 h-2.5" />
                Spoken
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs font-bold font-mono text-[var(--color-sentinel-text)] tabular-nums">
              ${amount.toLocaleString()}
            </span>
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] font-mono">
              (₹{(amount * 83).toLocaleString()})
            </span>
          </div>
        </div>
      </div>

      {/* 3. Transaction Channel */}
      <div className="flex items-center gap-3 p-3.5 rounded-xl bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border-subtle)] transition-all">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-[rgba(139,92,246,0.12)] text-[var(--color-accent-purple)]">
          <ArrowUpRight className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider block font-medium">
            Action Channel
          </span>
          <span className="text-xs font-semibold text-[var(--color-sentinel-text)] truncate block">
            {transferType}
          </span>
        </div>
      </div>

      {/* 4. Contextual Threat Modifier */}
      <div className="flex items-center gap-3 p-3.5 rounded-xl bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border-subtle)] transition-all">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
          isHighValue || isHighRisk
            ? 'bg-[rgba(245,197,66,0.12)] text-[var(--color-risk-medium)]'
            : 'bg-[rgba(0,229,200,0.12)] text-[var(--color-risk-low)]'
        }`}>
          {isHighValue || isHighRisk ? <AlertTriangle className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <span className="text-[10px] text-[var(--color-sentinel-text-dim)] uppercase tracking-wider block font-medium">
            Context Threat Modifier
          </span>
          <div className="flex items-center gap-1.5">
            <span className={`text-xs font-bold ${
              isHighValue || isHighRisk ? 'text-[var(--color-risk-medium)]' : 'text-[var(--color-risk-low)]'
            }`}>
              {isHighValue ? '+30% Risk Modifier' : 'Normal Context'}
            </span>
            <span className="text-[10px] text-[var(--color-sentinel-text-dim)] font-medium">
              · {riskLevel}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ContextRibbon;
