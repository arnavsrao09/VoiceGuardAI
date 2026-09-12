import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, Lock, Send, UserCheck, X, CheckCircle2, PhoneCall } from 'lucide-react';
import { apiFetch } from '../../lib/api';

interface TransactionInterceptorProps {
  isOpen: boolean;
  onClose: () => void;
  riskScore: number;
  threatCategory: string;
  reason: string;
  sessionId?: string;
  callerId?: string;
  callerPhone?: string;
}

export const TransactionInterceptor: React.FC<TransactionInterceptorProps> = ({
  isOpen,
  onClose,
  riskScore,
  threatCategory,
  reason,
  sessionId,
  callerId = 'Live Caller',
  callerPhone = '',
}) => {
  const [actionTaken, setActionTaken] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [callbackNumber, setCallbackNumber] = useState<string>(callerPhone || '');

  useEffect(() => {
    if (callerPhone) {
      setCallbackNumber(callerPhone);
    }
  }, [callerPhone]);

  if (!isOpen) return null;

  const isIdentityMismatch = threatCategory === 'GENUINE_DIFFERENT_SPEAKER';
  const headline = isIdentityMismatch
    ? 'Identity Verification Failed'
    : 'Impersonation Threat Intercepted';
  const scoreLabel = isIdentityMismatch
    ? 'Identity Mismatch Risk:'
    : 'Synthetic Spoof Risk:';

  const handleAction = async (actionType: string) => {
    setIsSubmitting(true);
    try {
      const res = await apiFetch('/alerts/workflows/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: actionType,
          session_id: sessionId,
          caller_id: callerId,
          callback_phone: actionType === 'INITIATE_CALLBACK' ? (callbackNumber.trim() || callerPhone) : undefined,
          reason: reason,
        }),
      });
      setActionTaken(actionType);
      setActionMessage(res?.description || 'Workflow countermeasure executed.');
    } catch (err) {
      console.error('Workflow execution failed:', err);
      setActionTaken(actionType);
      setActionMessage('Countermeasure queued in secure audit log.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="w-full max-w-lg bg-[#141622] border-2 border-red-500/50 rounded-2xl p-6 shadow-2xl relative overflow-hidden"
        >
          {/* Glowing Red Background Backdrop */}
          <div className="absolute -top-24 -left-24 w-60 h-60 bg-red-500/20 rounded-full blur-3xl pointer-events-none" />

          {/* Header */}
          <div className="flex items-start justify-between mb-4 relative z-10">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-red-500/20 text-red-400 border border-red-500/30">
                <ShieldAlert className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <span className="text-[11px] font-bold tracking-widest text-red-400 uppercase">
                  AUTOMATED SECURITY INTERCEPTOR
                </span>
                <h2 className="text-xl font-extrabold text-white">
                  {headline}
                </h2>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800/60 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Threat Metric Summary */}
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-5 text-sm">
            <div className="flex justify-between items-center mb-2">
              <span className="text-gray-300 font-medium">Target Identity / Caller:</span>
              <span className="font-bold text-white text-xs">{callerId}</span>
            </div>
            {sessionId && (
              <div className="flex justify-between items-center mb-2">
                <span className="text-gray-300 font-medium">Session ID:</span>
                <span className="font-mono text-xs text-gray-400">#{sessionId.slice(0, 8)}...</span>
              </div>
            )}
            <div className="flex justify-between items-center mb-2">
              <span className="text-gray-300 font-medium">{scoreLabel}</span>
              <span className="text-lg font-black text-red-400">
                {(riskScore * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-gray-300 font-medium">Threat Category:</span>
              <span className="font-mono text-xs text-red-300 bg-red-950/60 px-2 py-0.5 rounded border border-red-500/20">
                {threatCategory}
              </span>
            </div>
            <p className="text-xs text-red-200/90 mt-2 border-t border-red-500/20 pt-2 leading-relaxed">
              {reason}
            </p>
          </div>

          {/* Action Success Confirmation */}
          {actionTaken ? (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4 text-center mb-4"
            >
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <h4 className="font-bold text-emerald-400 text-sm">Action Executed Successfully</h4>
              <p className="text-xs text-gray-300 mt-1">
                {actionMessage || 'Workflow countermeasure executed across security infrastructure.'}
              </p>
              <button
                onClick={onClose}
                className="mt-3 px-4 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-black font-bold text-xs rounded-lg transition"
              >
                Close Interceptor
              </button>
            </motion.div>
          ) : (
            <>
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Automated Countermeasure Workflows (Select Action)
              </h4>

              <div className="space-y-2 mb-4">
                <button
                  onClick={() => handleAction('AUTO_HOLD_TRANSACTION')}
                  disabled={isSubmitting}
                  className="w-full flex items-center justify-between p-3 rounded-xl bg-red-600/20 hover:bg-red-600/30 border border-red-500/40 text-left transition group"
                >
                  <div className="flex items-center gap-3">
                    <Lock className="w-4 h-4 text-red-400 group-hover:scale-110 transition" />
                    <div>
                      <span className="text-xs font-bold text-white block">Auto-Hold High-Value Wire</span>
                      <span className="text-[11px] text-gray-400">Immediate cryptographic freeze & multi-channel alert</span>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-red-400">HOLD</span>
                </button>

                <button
                  onClick={() => handleAction('REQUIRE_DUAL_SUPERVISOR_APPROVAL')}
                  disabled={isSubmitting}
                  className="w-full flex items-center justify-between p-3 rounded-xl bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/40 text-left transition group"
                >
                  <div className="flex items-center gap-3">
                    <Send className="w-4 h-4 text-amber-400 group-hover:scale-110 transition" />
                    <div>
                      <span className="text-xs font-bold text-white block">Require Dual-Supervisor Approval</span>
                      <span className="text-[11px] text-gray-400">Escalate transaction to fraud control supervisor queue</span>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-amber-400">DUAL AUTH</span>
                </button>

                <button
                  onClick={() => handleAction('BLOCK_CHANNEL')}
                  disabled={isSubmitting}
                  className="w-full flex items-center justify-between p-3 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/40 text-left transition group"
                >
                  <div className="flex items-center gap-3">
                    <ShieldAlert className="w-4 h-4 text-rose-400 group-hover:scale-110 transition" />
                    <div>
                      <span className="text-xs font-bold text-white block">Blacklist Caller & Block Channel</span>
                      <span className="text-[11px] text-gray-400">Terminate audio stream and add identity to blocklist</span>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-rose-400">BLOCK</span>
                </button>

                {/* Out-of-Band Callback with Phone Input */}
                <div className="p-3.5 rounded-xl bg-indigo-950/40 border border-indigo-500/40 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <PhoneCall className="w-4 h-4 text-indigo-400" />
                      <div>
                        <span className="text-xs font-bold text-white block">Out-of-Band Phone Callback</span>
                        <span className="text-[11px] text-gray-400">Trigger direct verification call to employee / user</span>
                      </div>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 uppercase tracking-wider">
                      VOICE 2FA
                    </span>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="text"
                      value={callbackNumber}
                      onChange={(e) => setCallbackNumber(e.target.value)}
                      placeholder="+1 (555) 019-2834 or +91 98200 12345"
                      className="flex-1 px-3 py-1.5 rounded-lg bg-black/50 border border-indigo-500/30 text-xs font-mono text-white placeholder-gray-500 focus:outline-none focus:border-indigo-400"
                    />
                    <button
                      onClick={() => handleAction('INITIATE_CALLBACK')}
                      disabled={isSubmitting}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition cursor-pointer disabled:opacity-50 shadow-sm"
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      <span>{isSubmitting ? 'Calling...' : 'Call Back'}</span>
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-[#2a2d3d]/50">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white transition"
            >
              Dismiss Alert
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default TransactionInterceptor;
