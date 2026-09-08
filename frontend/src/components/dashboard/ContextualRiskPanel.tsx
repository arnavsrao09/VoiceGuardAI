import React from 'react';
import { MapPin, DollarSign, ArrowUpRight, Globe, Sparkles } from 'lucide-react';

interface ContextualRiskPanelProps {
  location?: string;
  amount?: number;
  transferType?: string;
  riskLevel?: string;
  riskScore?: number;
  isExtractedFromSpeech?: boolean;
}

export const ContextualRiskPanel: React.FC<ContextualRiskPanelProps> = ({
  location = 'Local Network (IN)',
  amount = 50000,
  transferType = 'High-Value Wire Transfer',
  riskLevel = 'LOW',
  riskScore = 0.15,
  isExtractedFromSpeech = false,
}) => {
  const isHighRisk = riskScore >= 0.60;
  const isHighValue = amount >= 25000;

  return (
    <div className="bg-[#141622]/80 backdrop-blur-md border border-[#2a2d3d] rounded-xl p-4 shadow-lg mb-6 transition-all">
      <div className="flex items-center justify-between pb-3 border-b border-[#2a2d3d]/60 mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
              Contextual Threat & Transaction Metadata
              {isExtractedFromSpeech && (
                <span className="flex items-center gap-1 text-[9px] font-bold text-cyan-400 normal-case px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                  <Sparkles className="w-3 h-3 text-cyan-400" />
                  LIVE EXTRACTED FROM SPEECH
                </span>
              )}
            </h3>
            <p className="text-[10px] text-gray-500">Live call telemetry feeding ML ensemble risk calculation</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isHighValue && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              HIGH VALUE
            </span>
          )}
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
              isHighRisk
                ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            }`}
          >
            {isHighRisk ? `RISK MODIFIER (+30%) · ${riskLevel}` : `NORMAL CONTEXT · ${riskLevel}`}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
        {/* Origin Geolocation */}
        <div className="p-3 rounded-lg bg-[#1a1c2a]/60 border border-[#2a2d3d]/40 flex flex-col justify-between">
          <div className="flex items-center gap-2.5 mb-1.5">
            <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-400 shrink-0">
              <MapPin className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400 block font-medium">Caller Geolocation</span>
              <span className="text-xs font-semibold text-gray-200">{location}</span>
            </div>
          </div>
          <span className="text-[9px] text-gray-500">Auto-resolved from WebRTC routing telemetry</span>
        </div>

        {/* Transaction Amount */}
        <div className="p-3 rounded-lg bg-[#1a1c2a]/60 border border-[#2a2d3d]/40 flex flex-col justify-between">
          <div className="flex items-center gap-2.5 mb-1.5">
            <div className="p-2 rounded-md bg-cyan-500/10 text-cyan-400 shrink-0">
              <DollarSign className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[10px] text-gray-400 block font-medium">Target Amount</span>
              <span className="text-xs font-semibold text-gray-200">
                ${amount.toLocaleString()} <span className="text-[10px] text-gray-400 font-normal">(₹{(amount * 83).toLocaleString()})</span>
              </span>
            </div>
          </div>
          <span className="text-[9px] text-cyan-400/80 font-medium">
            {isExtractedFromSpeech ? '✓ Parsed automatically from spoken words' : 'Awaiting live voice instruction...'}
          </span>
        </div>

        {/* Transfer Type */}
        <div className="p-3 rounded-lg bg-[#1a1c2a]/60 border border-[#2a2d3d]/40 flex flex-col justify-between">
          <div className="flex items-center gap-2.5 mb-1.5">
            <div className="p-2 rounded-md bg-purple-500/10 text-purple-400 shrink-0">
              <ArrowUpRight className="w-4 h-4" />
            </div>
            <div className="min-w-0 flex-1">
              <span className="text-[10px] text-gray-400 block font-medium">Transaction Channel</span>
              <span className="text-xs font-semibold text-gray-200 truncate block">{transferType}</span>
            </div>
          </div>
          <span className="text-[9px] text-purple-400/80 font-medium">
            {isExtractedFromSpeech ? '✓ Action intent classified from dialogue' : 'Dynamic intent classification'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ContextualRiskPanel;
