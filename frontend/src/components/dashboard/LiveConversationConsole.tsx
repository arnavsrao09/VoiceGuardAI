import React, { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../../lib/config';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Mic, Sparkles, AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react';

export interface SttLanguage {
  code: string;
  name: string;
  nativeName: string;
}

export const SUPPORTED_STT_LANGUAGES: SttLanguage[] = [
  { code: 'te-IN', name: 'Telugu', nativeName: 'తెలుగు' },
  { code: 'kn-IN', name: 'Kannada', nativeName: 'ಕನ್ನಡ' },
  { code: 'hi-IN', name: 'Hindi', nativeName: 'हिंदी' },
  { code: 'ta-IN', name: 'Tamil', nativeName: 'தமிழ்' },
  { code: 'en-IN', name: 'English (India)', nativeName: 'Indian English' },
  { code: 'en-US', name: 'English (US)', nativeName: 'English' },
  { code: 'bn-IN', name: 'Bengali', nativeName: 'বাংলা' },
  { code: 'mr-IN', name: 'Marathi', nativeName: 'मराठी' },
];

interface Utterance {
  id: string;
  sender: 'Caller';
  text: string;
  timestamp: string;
  extractedAmount?: number | null;
  extractedChannel?: string | null;
  urgencyLevel?: string;
  urgencyCues?: string[];
  coercionCues?: string[];
}

interface LiveConversationConsoleProps {
  isMonitoring: boolean;
  onIntentExtracted?: (intent: {
    amount?: number | null;
    channel?: string;
    urgencyLevel?: string;
    summary?: string;
  }) => void;
}

export const LiveConversationConsole: React.FC<LiveConversationConsoleProps> = ({
  isMonitoring,
  onIntentExtracted,
}) => {
  const [transcriptHistory, setTranscriptHistory] = useState<Utterance[]>([]);
  const [interimText, setInterimText] = useState<string>('');
  const [isRecognizing, setIsRecognizing] = useState<boolean>(false);
  const [hasSpeechSupport, setHasSpeechSupport] = useState<boolean>(true);
  const [lastAnalyzedSummary, setLastAnalyzedSummary] = useState<string | null>(null);
  const [sttLang] = useState<string>('en-US');

  const recognitionRef = useRef<any>(null);
  const sttLangRef = useRef<string>(sttLang);
  const isMonitoringRef = useRef<boolean>(isMonitoring);
  const restartTimerRef = useRef<number | null>(null);

  useEffect(() => {
    sttLangRef.current = sttLang;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.lang = sttLang;
      } catch {
        // Ignored
      }
    }
  }, [sttLang]);

  useEffect(() => {
    isMonitoringRef.current = isMonitoring;
  }, [isMonitoring]);

  // Helper to send text to backend intent extractor
  const processTranscript = async (textToAnalyze: string) => {
    if (!textToAnalyze.trim()) return;

    try {
      const res = await fetch(`${API_BASE_URL}/telephony/analyze-conversation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textToAnalyze }),
      });

      if (res.ok) {
        const data = await res.json();
        const newUtterance: Utterance = {
          id: Math.random().toString(36).substring(2, 9),
          sender: 'Caller',
          text: textToAnalyze,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          extractedAmount: data.detected_amount,
          extractedChannel: data.detected_channel,
          urgencyLevel: data.urgency_level,
          urgencyCues: data.urgency_cues,
          coercionCues: data.coercion_cues,
        };

        setTranscriptHistory((prev) => [...prev.slice(-15), newUtterance]);

        if (data.intent_summary) {
          setLastAnalyzedSummary(data.intent_summary);
        }

        if (onIntentExtracted) {
          onIntentExtracted({
            amount: data.detected_amount,
            channel: data.detected_channel,
            urgencyLevel: data.urgency_level,
            summary: data.intent_summary,
          });
        }
      }
    } catch (err) {
      console.error('[STT] Failed to analyze conversation intent:', err);
    }
  };

  // Initialize Web Speech Recognition
  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setHasSpeechSupport(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = sttLangRef.current || 'en-US';

    recognition.onstart = () => {
      setIsRecognizing(true);
    };

    recognition.onerror = (event: any) => {
      if (event.error === 'no-speech' || event.error === 'aborted') {
        return;
      }
      if (event.error === 'audio-capture' || event.error === 'not-allowed') {
        console.warn('[LiveSTT] Mic access issue:', event.error);
        setIsRecognizing(false);
        return;
      }
      console.warn('[LiveSTT] Recognition error:', event.error);
    };

    recognition.onend = () => {
      setIsRecognizing(false);
      // Auto-restart if still monitoring (handle silence timeouts safely)
      if (isMonitoringRef.current) {
        if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
        restartTimerRef.current = window.setTimeout(() => {
          if (isMonitoringRef.current && recognitionRef.current) {
            try {
              recognitionRef.current.lang = sttLangRef.current || 'en-US';
              recognitionRef.current.start();
            } catch {
              // Ignored
            }
          }
        }, 200);
      }
    };

    recognition.onresult = async (event: any) => {
      let currentInterim = '';
      let finalSpeechChunk = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalSpeechChunk += event.results[i][0].transcript;
        } else {
          currentInterim += event.results[i][0].transcript;
        }
      }

      setInterimText(currentInterim);

      if (finalSpeechChunk.trim()) {
        const textToAnalyze = finalSpeechChunk.trim();
        setInterimText('');
        processTranscript(textToAnalyze);
      }
    };

    recognitionRef.current = recognition;

    return () => {
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      try {
        recognition.stop();
      } catch {
        // Ignored
      }
    };
  }, [onIntentExtracted]);

  // Start / Stop speech recognition based on monitoring status
  useEffect(() => {
    if (!recognitionRef.current) return;

    if (isMonitoring) {
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      try {
        recognitionRef.current.lang = sttLangRef.current || 'en-US';
        recognitionRef.current.start();
      } catch {
        // Ignored if already started
      }
    } else {
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      try {
        recognitionRef.current.stop();
        setInterimText('');
        setIsRecognizing(false);
      } catch {
        // Ignored
      }
    }
  }, [isMonitoring]);

  return (
    <div className="rounded-2xl border border-[#2a2d3d] bg-[#141622]/90 backdrop-blur-md overflow-hidden mb-6 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2d3d]/60 bg-[#1a1c2a]/40">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${isMonitoring ? 'bg-cyan-500/15 text-cyan-400' : 'bg-gray-800 text-gray-500'} transition-all`}>
            <MessageSquare className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider flex items-center gap-2">
              Live Conversation Tracking & Automated Intent Extraction
              {isMonitoring && isRecognizing && (
                <span className="flex items-center gap-1 text-[9px] font-bold text-cyan-400 normal-case tracking-normal px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  REAL-TIME STT ACTIVE
                </span>
              )}
            </h3>
            <p className="text-[10px] text-gray-400 mt-0.5">
              Listens to live caller speech, auto-transcribes conversation, and extracts transaction amount & action.
            </p>
          </div>
        </div>

        {lastAnalyzedSummary && (
          <div className="hidden lg:flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-[10px] text-indigo-300">
            <Sparkles className="w-3 h-3 text-indigo-400 shrink-0" />
            <span className="font-semibold truncate max-w-xs">{lastAnalyzedSummary}</span>
          </div>
        )}
      </div>

      {/* Transcript Area */}
      <div className="p-5">
        {!hasSpeechSupport && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs mb-4">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>Browser speech recognition is not supported in this environment. Please use Chrome, Edge, or Safari.</span>
          </div>
        )}

        <div className="space-y-3 max-h-56 overflow-y-auto pr-1">
          {transcriptHistory.length === 0 && !interimText && (
            <div className="py-8 text-center rounded-xl border border-dashed border-[#2a2d3d]/60 bg-[#1a1c2a]/20">
              <Mic className={`w-6 h-6 mx-auto mb-2 ${isMonitoring ? 'text-cyan-400 animate-bounce' : 'text-gray-600'}`} />
              <p className="text-xs font-semibold text-gray-400">
                {isMonitoring
                  ? 'Listening to live speech... Speak naturally (e.g. "I want to wire transfer $50,000 immediately")'
                  : 'Start monitoring to begin live speech-to-text and automated intent extraction.'}
              </p>
              <p className="text-[10px] text-gray-500 mt-1">
                Zero simulation · Automatically parses transaction values, channels, and coercion tactics.
              </p>
            </div>
          )}

          {transcriptHistory.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-3 rounded-xl bg-[#1a1c2a]/70 border border-[#2a2d3d]/50 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between text-[10px] text-gray-500">
                <span className="font-bold text-gray-300 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  {item.sender}
                </span>
                <span>{item.timestamp}</span>
              </div>

              <p className="text-xs text-gray-200 leading-relaxed font-medium">
                "{item.text}"
              </p>

              {/* Extracted Intent Badges */}
              {(item.extractedAmount || item.extractedChannel || (item.urgencyCues && item.urgencyCues.length > 0)) && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-[#2a2d3d]/40">
                  {item.extractedAmount && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-[10px] font-bold">
                      <CheckCircle2 className="w-3 h-3 text-cyan-400" />
                      Amount: ${item.extractedAmount.toLocaleString()}
                    </span>
                  )}
                  {item.extractedChannel && (
                    <span className="px-2 py-0.5 rounded-md bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[10px] font-bold">
                      Channel: {item.extractedChannel}
                    </span>
                  )}
                  {item.urgencyLevel && item.urgencyLevel !== 'NORMAL' && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-500/15 border border-red-500/30 text-red-300 text-[10px] font-bold">
                      <ShieldAlert className="w-3 h-3 text-red-400" />
                      Pressure Cues: {item.urgencyCues?.join(', ')}
                    </span>
                  )}
                </div>
              )}
            </motion.div>
          ))}

          {/* Interim Real-Time Speech Stream */}
          <AnimatePresence>
            {interimText && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="p-3 rounded-xl bg-cyan-500/5 border border-cyan-500/30 text-cyan-300 text-xs italic flex items-center gap-2"
              >
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping shrink-0" />
                <span className="truncate">{interimText}...</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default LiveConversationConsole;
