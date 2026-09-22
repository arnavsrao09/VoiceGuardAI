import React, { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '../../lib/config';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Globe,
  Fingerprint,
  AlertTriangle,
  MessageSquare,
  Mic,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  ShieldAlert,
  Send,
  Languages,
  RefreshCw,
  PhoneCall,
  Radio,
  Square,
} from 'lucide-react';

export interface CallerGeoData {
  ip: string;
  city: string;
  region: string;
  country: string;
  country_code: string;
  isp: string;
  org: string;
  timezone: string;
  lat: number;
  lon: number;
  threat_flag: string;
}

export interface Utterance {
  id: string;
  sender: 'Caller' | 'Agent';
  text: string;
  timestamp: string;
  extractedAmount?: number | null;
  extractedChannel?: string;
  urgencyLevel?: string;
  urgencyCues?: string[];
  coercionCues?: string[];
}

export interface LiveCallIntelligenceStudioProps {
  isMonitoring: boolean;
  onIntentExtracted?: (intent: {
    amount?: number | null;
    channel?: string;
    urgencyLevel?: string;
    summary?: string;
  }) => void;
  onCallStart?: (geoData: CallerGeoData) => void;
  onCallerIdentified?: (callerPhone: string, callerName?: string) => void;
  onTriggerCallMonitoring?: () => void;
}

const SUPPORTED_LANGUAGES = [
  { code: 'en-US', label: 'English (US)' },
  { code: 'en-IN', label: 'English (India)' },
  { code: 'te-IN', label: 'Telugu (తెలుగు)' },
  { code: 'hi-IN', label: 'Hindi (हिंदी)' },
  { code: 'ta-IN', label: 'Tamil (தமிழ்)' },
  { code: 'kn-IN', label: 'Kannada (ಕನ್ನಡ)' },
];

const SAMPLE_PHRASES = [
  'I need to wire $10,000 to my account urgently',
  'Transfer 25k immediately to beneficiary',
  'Send 50000 rupees for my hospital bill',
  'Please reset my banking password and PIN',
];

export const LiveCallIntelligenceStudio: React.FC<LiveCallIntelligenceStudioProps> = ({
  isMonitoring,
  onIntentExtracted,
  onCallStart,
  onCallerIdentified,
  onTriggerCallMonitoring,
}) => {
  // Asterisk PBX state
  const [asteriskStatus, setAsteriskStatus] = useState<any>(null);
  const [isSimulatingCall, setIsSimulatingCall] = useState<boolean>(false);
  const [simulatedCallId, setSimulatedCallId] = useState<string | null>(null);
  const [simPhoneInput, setSimPhoneInput] = useState<string>('+91 98200 12345');
  const [simScenario, setSimScenario] = useState<string>('deepfake_pressure');

  // Speech-to-text state
  const [transcriptHistory, setTranscriptHistory] = useState<Utterance[]>([]);
  const [interimText, setInterimText] = useState<string>('');
  const [isRecognizing, setIsRecognizing] = useState<boolean>(false);
  const [hasSpeechSupport, setHasSpeechSupport] = useState<boolean>(true);
  const [sttLang, setSttLang] = useState<string>('en-US');
  const [manualInput, setManualInput] = useState<string>('');
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);

  // Telephony & Device state
  const [isLoadingGeo, setIsLoadingGeo] = useState<boolean>(false);
  const [geoData, setGeoData] = useState<CallerGeoData | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [deviceInfo, setDeviceInfo] = useState<{
    browser: string;
    os: string;
    screen: string;
    audioDevices: number;
  } | null>(null);

  const recognitionRef = useRef<any>(null);
  const sttLangRef = useRef<string>(sttLang);
  const isMonitoringRef = useRef<boolean>(isMonitoring);
  const restartTimerRef = useRef<number | null>(null);
  const transcriptScrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll transcript window on new utterances or interim speech
  useEffect(() => {
    if (transcriptScrollRef.current) {
      transcriptScrollRef.current.scrollTop = transcriptScrollRef.current.scrollHeight;
    }
  }, [transcriptHistory, interimText]);

  // Sync refs and handle dynamic language switching
  useEffect(() => {
    sttLangRef.current = sttLang;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.lang = sttLang;
        if (isMonitoringRef.current && isRecognizing) {
          try {
            recognitionRef.current.stop();
          } catch {
            // Will auto-restart in onend with new language
          }
        }
      } catch {
        // Ignored
      }
    }
  }, [sttLang, isRecognizing]);

  useEffect(() => {
    isMonitoringRef.current = isMonitoring;
  }, [isMonitoring]);

  // Detect device specs on mount
  useEffect(() => {
    const detectDevice = async () => {
      const ua = navigator.userAgent;
      let browser = 'Chrome';
      let os = 'Unknown';

      if (ua.includes('Chrome') && !ua.includes('Edg')) browser = 'Chrome';
      else if (ua.includes('Firefox')) browser = 'Firefox';
      else if (ua.includes('Safari') && !ua.includes('Chrome')) browser = 'Safari';
      else if (ua.includes('Edg')) browser = 'Edge';

      if (ua.includes('Windows')) os = 'Windows';
      else if (ua.includes('Mac OS')) os = 'macOS';
      else if (ua.includes('Linux')) os = 'Linux';
      else if (ua.includes('Android')) os = 'Android';
      else if (ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS';

      let audioDevices = 1;
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        audioDevices = devices.filter((d) => d.kind === 'audioinput').length || 1;
      } catch {
        audioDevices = 1;
      }

      setDeviceInfo({
        browser,
        os,
        screen: `${window.screen.width}×${window.screen.height}`,
        audioDevices,
      });
    };
    detectDevice();
  }, []);

  // Fetch caller geo data
  const fetchGeoLocation = useCallback(async (targetIp?: string) => {
    setIsLoadingGeo(true);
    setGeoError(null);
    try {
      const url = targetIp
        ? `${API_BASE_URL}/telephony/caller-metadata?ip=${encodeURIComponent(targetIp)}`
        : `${API_BASE_URL}/telephony/caller-metadata`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CallerGeoData = await res.json();
      setGeoData(data);
      if (onCallStart) onCallStart(data);
    } catch (err) {
      setGeoError('Unable to connect to telephony service');
      console.error('[TelephonyStudio] Geo fetch error:', err);
    } finally {
      setIsLoadingGeo(false);
    }
  }, [onCallStart]);

  const fetchAsteriskStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/telephony/asterisk/status`);
      if (res.ok) {
        const data = await res.json();
        setAsteriskStatus(data);
      }
    } catch {
      // Backend status polling
    }
  }, []);

  useEffect(() => {
    fetchGeoLocation();
    fetchAsteriskStatus();
    const interval = setInterval(fetchAsteriskStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchGeoLocation, fetchAsteriskStatus]);

  const handleStartSimulatedCall = async () => {
    setIsSimulatingCall(true);
    try {
      if (onCallerIdentified) {
        onCallerIdentified(simPhoneInput, 'Simulated Inbound SIP');
      }

      const res = await fetch(`${API_BASE_URL}/telephony/asterisk/simulate-call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          caller_phone: simPhoneInput,
          caller_name: 'Rajesh Sharma (HDFC Wire)',
          amount: 50000.0,
          scenario: simScenario,
          duration_seconds: 20,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSimulatedCallId(data.call_id);
        fetchAsteriskStatus();
        if (onTriggerCallMonitoring && !isMonitoring) {
          onTriggerCallMonitoring();
        }
      }
    } catch (err) {
      console.error('Failed to trigger simulated Asterisk call:', err);
    } finally {
      setIsSimulatingCall(false);
    }
  };

  const handleHangupSimulatedCall = async () => {
    if (!simulatedCallId) return;
    try {
      await fetch(`${API_BASE_URL}/telephony/asterisk/hangup/${simulatedCallId}`, {
        method: 'POST',
      });
      setSimulatedCallId(null);
      fetchAsteriskStatus();
    } catch (err) {
      console.error('Failed to hangup simulated call:', err);
    }
  };

  // Intent Analysis function
  const processTranscript = async (textToAnalyze: string) => {
    if (!textToAnalyze.trim()) return;
    setIsAnalyzing(true);

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

        setTranscriptHistory((prev) => [...prev.slice(-10), newUtterance]);

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
      console.error('[TelephonyStudio] Intent analysis error:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Setup Web Speech Recognition with persistent auto-reconnect
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
      // Benign speech recognition events (silence or aborts)
      if (event.error === 'no-speech' || event.error === 'aborted') {
        return;
      }
      if (event.error === 'audio-capture' || event.error === 'not-allowed') {
        console.warn('[LiveSTT] Microphone access issue:', event.error);
        setIsRecognizing(false);
        return;
      }
      console.warn('[LiveSTT] SpeechRecognition event:', event.error);
    };

    recognition.onend = () => {
      setIsRecognizing(false);
      // Auto-restart if monitoring remains active (handle browser silence timeouts safely)
      if (isMonitoringRef.current) {
        if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
        restartTimerRef.current = window.setTimeout(() => {
          if (isMonitoringRef.current && recognitionRef.current) {
            try {
              recognitionRef.current.lang = sttLangRef.current || 'en-US';
              recognitionRef.current.start();
            } catch {
              // Ignore if already active or busy
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
  }, []);

  // Trigger speech recognition on monitoring toggle (SIP call or mic stream)
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
        // Already active or queued
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

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualInput.trim()) {
      processTranscript(manualInput.trim());
      setManualInput('');
    }
  };

  const isDomestic = geoData?.threat_flag === 'DOMESTIC';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 mb-5">
      {/* ── Left (col-span-8): Live Conversation STT & Intent Extraction ── */}
      <div className="lg:col-span-8 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 flex flex-col justify-between min-h-[480px]">
        <div className="flex-1 flex flex-col min-h-0">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3.5 border-b border-[var(--color-sentinel-border-subtle)] mb-4">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[var(--color-accent-primary-dim)] text-[var(--color-accent-primary)]">
                <MessageSquare className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)] flex items-center gap-2">
                  Live Conversation STT & Intent Extraction
                  {isMonitoring && (
                    <span className="flex items-center gap-1 text-[9px] font-bold text-[var(--color-accent-primary)] px-2 py-0.5 rounded-full bg-[var(--color-accent-primary-dim)] border border-[var(--color-accent-primary)]/20">
                      <span className={`w-1.5 h-1.5 rounded-full ${isRecognizing ? 'bg-[var(--color-accent-primary)] animate-pulse' : 'bg-[var(--color-accent-primary)]'}`} />
                      {isRecognizing ? 'STT ACTIVE' : 'LISTENING'}
                    </span>
                  )}
                </h3>
                <p className="text-xs text-[var(--color-sentinel-text-dim)] pt-2">
                  Real-time voice stream transcription, money amount extraction & coercion detection
                </p>
              </div>
            </div>

            {/* Language Switcher */}
            <div className="flex items-center gap-1.5 text-xs text-[var(--color-sentinel-text-muted)]">
              <Languages className="w-3.5 h-3.5 text-[var(--color-accent-primary)]" />
              <select
                value={sttLang}
                onChange={(e) => setSttLang(e.target.value)}
                className="px-2.5 py-1 rounded-lg bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)] text-xs font-medium text-[var(--color-sentinel-text)] focus:outline-none focus:border-[var(--color-accent-primary)] transition-colors cursor-pointer"
              >
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {!hasSpeechSupport && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs mb-3">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Browser Web Speech API is not supported in this browser. Please use Chrome, Edge, or Safari, or test using the sample chips below.</span>
            </div>
          )}

          {/* Quick Voice Test Samples */}
          <div className="flex flex-wrap items-center gap-2 mb-3.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-sentinel-text-dim)] flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-[var(--color-accent-primary)]" />
              Quick Voice Samples:
            </span>
            {SAMPLE_PHRASES.map((phrase, idx) => (
              <button
                key={idx}
                onClick={() => processTranscript(phrase)}
                disabled={isAnalyzing}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-[var(--color-sentinel-surface-2)] hover:bg-[var(--color-sentinel-surface-3)] border border-[var(--color-sentinel-border-subtle)] hover:border-[var(--color-accent-primary)]/40 text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] transition-all font-medium disabled:opacity-50"
              >
                "{phrase}"
              </button>
            ))}
          </div>

          {/* Transcript / Utterances Stream (Expanded to full chat container height) */}
          <div ref={transcriptScrollRef} className="flex-1 min-h-[300px] max-h-[480px] overflow-y-auto pr-1 mb-4 space-y-2.5 scroll-smooth">
            {transcriptHistory.length === 0 && !interimText && (
              <div className="h-full flex flex-col items-center justify-center p-8 text-center rounded-xl border border-dashed border-[var(--color-sentinel-border-subtle)] bg-[var(--color-sentinel-surface-2)]/40 min-h-[260px]">
                <Mic className={`w-6 h-6 mx-auto mb-2 ${isMonitoring ? 'text-[var(--color-accent-primary)] animate-pulse' : 'text-[var(--color-sentinel-text-dim)]'}`} />
                <p className="text-xs font-semibold text-[var(--color-sentinel-text)] max-w-sm">
                  {isMonitoring
                    ? 'Listening to live voice stream... Speak transaction details naturally'
                    : 'Start monitoring or click any sample prompt above to test automated intent extraction.'}
                </p>
                <p className="text-[10px] text-[var(--color-sentinel-text-dim)] mt-1 max-w-xs">
                  Parses dollar amounts, Indian rupees, wire requests, and urgent pressure tactics in real time.
                </p>
              </div>
            )}

            {transcriptHistory.map((item) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-3 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] flex flex-col gap-1.5"
              >
                <div className="flex items-center justify-between text-[10px] text-[var(--color-sentinel-text-dim)]">
                  <span className="font-bold text-[var(--color-sentinel-text-muted)] flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    {item.sender}
                  </span>
                  <span className="font-mono">{item.timestamp}</span>
                </div>

                <p className="text-xs text-[var(--color-sentinel-text)] leading-relaxed font-medium">
                  "{item.text}"
                </p>

                {(item.extractedAmount || item.extractedChannel || (item.urgencyCues && item.urgencyCues.length > 0)) && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-[var(--color-sentinel-border-subtle)]">
                    {item.extractedAmount && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--color-accent-primary-dim)] border border-[var(--color-accent-primary)]/30 text-[var(--color-accent-primary)] text-[10px] font-bold font-mono">
                        <CheckCircle2 className="w-3 h-3" />
                        Amount: ${item.extractedAmount.toLocaleString()}
                      </span>
                    )}
                    {item.extractedChannel && (
                      <span className="px-2 py-0.5 rounded-md bg-[rgba(139,92,246,0.15)] border border-[rgba(139,92,246,0.3)] text-[var(--color-accent-purple)] text-[10px] font-bold">
                        Channel: {item.extractedChannel}
                      </span>
                    )}
                    {item.urgencyLevel && item.urgencyLevel !== 'NORMAL' && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-500/15 border border-red-500/30 text-red-300 text-[10px] font-bold">
                        <ShieldAlert className="w-3 h-3 text-red-400" />
                        Pressure Flags: {item.urgencyCues?.join(', ')}
                      </span>
                    )}
                  </div>
                )}
              </motion.div>
            ))}

            <AnimatePresence>
              {interimText && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="p-2.5 rounded-xl bg-[var(--color-accent-primary-dim)] border border-[var(--color-accent-primary)]/30 text-[var(--color-accent-primary)] text-xs italic flex items-center gap-2"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent-primary)] animate-ping shrink-0" />
                  <span className="truncate">{interimText}...</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Manual Input Form */}
        <form onSubmit={handleManualSubmit} className="flex items-center gap-2 pt-2 border-t border-[var(--color-sentinel-border-subtle)]">
          <input
            type="text"
            value={manualInput}
            onChange={(e) => setManualInput(e.target.value)}
            placeholder="Type or paste any spoken caller phrase (e.g. 'I want to transfer 15000 dollars now')..."
            className="flex-1 px-3.5 py-2 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)] text-xs text-[var(--color-sentinel-text)] placeholder-[var(--color-sentinel-text-dim)] focus:outline-none focus:border-[var(--color-accent-primary)] transition-colors"
          />
          <button
            type="submit"
            disabled={!manualInput.trim() || isAnalyzing}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[var(--color-accent-primary)] text-[var(--color-sentinel-bg)] text-xs font-bold hover:brightness-110 disabled:opacity-50 transition-all shrink-0 cursor-pointer shadow-md"
          >
            <Send className="w-3.5 h-3.5" />
            Analyze Intent
          </button>
        </form>
      </div>

      {/* ── Right (col-span-4): Telephony & Device Specs ── */}
      <div className="lg:col-span-4 rounded-2xl border border-[var(--color-sentinel-border)] bg-[var(--color-sentinel-surface)] p-5 flex flex-col justify-between">
        <div>
          {/* Header */}
          <div className="flex items-center justify-between pb-3.5 border-b border-[var(--color-sentinel-border-subtle)] mb-4">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[rgba(139,92,246,0.12)] text-[var(--color-accent-purple)]">
                <Globe className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-sentinel-text)]">
                  Call Telemetry & Device
                </h3>
                <p className="text-xs text-[var(--color-sentinel-text-dim)] pt-2">
                  Carrier network & hardware fingerprint
                </p>
              </div>
            </div>

            <button
              onClick={() => fetchGeoLocation()}
              disabled={isLoadingGeo}
              className="p-1.5 rounded-lg text-[var(--color-sentinel-text-dim)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)] transition-colors border border-[var(--color-sentinel-border-subtle)]"
              title="Refresh Telemetry"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingGeo ? 'animate-spin text-[var(--color-accent-primary)]' : ''}`} />
            </button>
          </div>

          {geoError ? (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300 mb-3">
              <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
              <span>{geoError}</span>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Geolocation Specs */}
              <div className="p-3 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] space-y-2">
                <div className="flex items-center justify-between pb-1.5 border-b border-[var(--color-sentinel-border-subtle)]">
                  <span className="text-[10px] font-bold text-[var(--color-sentinel-text-dim)] uppercase tracking-wider">
                    Origin Geolocation
                  </span>
                  {geoData && (
                    <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                      isDomestic
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-red-500/10 text-red-400 border border-red-500/20'
                    }`}>
                      {isDomestic ? '🇮🇳 DOMESTIC' : '🌐 INTERNATIONAL'}
                    </span>
                  )}
                </div>

                {geoData ? (
                  <div className="space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-sentinel-text-dim)] text-[11px]">Location</span>
                      <span className="font-semibold text-[var(--color-sentinel-text)]">{geoData.city}, {geoData.region}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-sentinel-text-dim)] text-[11px]">Carrier / ISP</span>
                      <span className="font-semibold text-[var(--color-sentinel-text)] truncate max-w-[140px]">{geoData.isp}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-sentinel-text-dim)] text-[11px]">IP Address</span>
                      <span className="font-mono font-semibold text-[var(--color-accent-primary)]">{geoData.ip}</span>
                    </div>
                  </div>
                ) : (
                  <div className="py-2 text-center text-xs text-[var(--color-sentinel-text-dim)]">Resolving telemetry...</div>
                )}
              </div>

              {/* Hardware Fingerprint */}
              <div className="p-3 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] space-y-2">
                <div className="flex items-center justify-between pb-1.5 border-b border-[var(--color-sentinel-border-subtle)]">
                  <div className="flex items-center gap-1.5">
                    <Fingerprint className="w-3.5 h-3.5 text-[var(--color-accent-purple)]" />
                    <span className="text-[10px] font-bold text-[var(--color-sentinel-text-dim)] uppercase tracking-wider">
                      Hardware Profile
                    </span>
                  </div>
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-[var(--color-accent-primary-dim)] text-[var(--color-accent-primary)] border border-[var(--color-accent-primary)]/20">
                    WEBRTC PCM
                  </span>
                </div>

                {deviceInfo ? (
                  <div className="space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-sentinel-text-dim)] text-[11px]">Browser & OS</span>
                      <span className="font-semibold text-[var(--color-sentinel-text)]">{deviceInfo.browser} / {deviceInfo.os}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-sentinel-text-dim)] text-[11px]">Audio Inputs</span>
                      <span className="font-semibold text-[var(--color-sentinel-text)]">{deviceInfo.audioDevices} microphone(s)</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-sentinel-text-dim)] text-[11px]">Screen Res</span>
                      <span className="font-mono text-[var(--color-sentinel-text-muted)]">{deviceInfo.screen}</span>
                    </div>
                  </div>
                ) : (
                  <div className="py-2 text-center text-xs text-[var(--color-sentinel-text-dim)]">Detecting hardware...</div>
                )}
              </div>

              {/* Asterisk PBX & ARI Inbound Gateway Card */}
              <div className="p-3 rounded-xl bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border-subtle)] space-y-2.5">
                <div className="flex items-center justify-between pb-1.5 border-b border-[var(--color-sentinel-border-subtle)]">
                  <div className="flex items-center gap-1.5">
                    <Radio className="w-3.5 h-3.5 text-cyan-400" />
                    <span className="text-[10px] font-bold text-[var(--color-sentinel-text-dim)] uppercase tracking-wider">
                      Asterisk PBX / ARI
                    </span>
                  </div>
                  <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                    simulatedCallId || asteriskStatus?.total_active_calls > 0
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 animate-pulse'
                      : 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/20'
                  }`}>
                    {simulatedCallId || asteriskStatus?.total_active_calls > 0
                      ? 'INBOUND CALL ACTIVE'
                      : asteriskStatus?.sip_server?.registered_clients?.length > 0
                      ? `MOBILE READY (${asteriskStatus.sip_server.registered_clients[0]})`
                      : 'ARI READY :8088'}
                  </span>
                </div>

                {/* Mobile / Desktop Softphone Connected Banner */}
                {asteriskStatus?.sip_server?.registered_clients?.length > 0 && (
                  <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 space-y-2">
                    <div className="flex items-center justify-between text-[11px] text-emerald-300">
                      <span className="flex items-center gap-1.5 font-bold">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                        Softphone Registered ({asteriskStatus.sip_server.registered_clients[0]})
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                        DIAL: 5000
                      </span>
                    </div>

                    {asteriskStatus?.sip_server?.active_calls_count > 0 ? (
                      <div className="p-2 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-[11px] space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-white font-semibold flex items-center gap-2">
                            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                            Live Audio Stream Active
                          </span>
                          <span className="font-mono text-emerald-400 font-bold text-xs">
                            {asteriskStatus?.sip_server?.active_calls?.[0]?.packet_count || 0} pkts
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[10px] text-emerald-200/80 font-mono">
                          <span>
                            MIC LEVEL {(Number(asteriskStatus?.sip_server?.active_calls?.[0]?.audio_rms || 0) * 100).toFixed(1)}%
                          </span>
                          <span>
                            {asteriskStatus?.sip_server?.active_calls?.[0]?.payload_type === 0
                              ? 'PCMU'
                              : asteriskStatus?.sip_server?.active_calls?.[0]?.payload_type === 8
                                ? 'PCMA'
                                : 'CODEC PENDING'} · RTP decoded
                          </span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-[10px] text-emerald-300/80 leading-relaxed">
                        To test your voice: Dial <strong className="text-white">5000</strong> in Zoiper and start speaking. VoiceGuard will decode and analyze your microphone in real-time.
                      </p>
                    )}
                  </div>
                )}

                {/* Simulated SIP Call Controls */}
                <div className="space-y-2.5 pt-1">
                  <span className="text-[10px] font-bold text-[var(--color-sentinel-text-dim)] uppercase tracking-wider block">
                    Or Test With Simulated Inbound Call
                  </span>

                  <div className="space-y-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-[var(--color-sentinel-text-dim)]">
                        Caller Phone Number
                      </label>
                      <input
                        type="text"
                        value={simPhoneInput}
                        onChange={(e) => setSimPhoneInput(e.target.value)}
                        placeholder="+91 98200 12345"
                        className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border)] text-xs font-mono text-[var(--color-sentinel-text)] focus:outline-none focus:border-cyan-400"
                      />
                    </div>

                    <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-[var(--color-sentinel-text-dim)]">
                        Scenario Benchmark
                      </label>
                      <select
                        value={simScenario}
                        onChange={(e) => setSimScenario(e.target.value)}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-[var(--color-sentinel-surface)] border border-[var(--color-sentinel-border)] text-xs text-[var(--color-sentinel-text)] focus:outline-none focus:border-cyan-400 cursor-pointer"
                      >
                        <option value="deepfake_pressure">Deepfake Pressure (High Threat Simulation)</option>
                        <option value="genuine_user">Genuine Human Caller (Safe Baseline)</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    {!simulatedCallId ? (
                      <button
                        onClick={handleStartSimulatedCall}
                        disabled={isSimulatingCall}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-xs font-bold transition shadow-sm cursor-pointer disabled:opacity-50"
                      >
                        <PhoneCall className="w-3.5 h-3.5" />
                        {isSimulatingCall ? 'Connecting SIP...' : 'Trigger Simulated SIP Call'}
                      </button>
                    ) : (
                      <button
                        onClick={handleHangupSimulatedCall}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 text-xs font-bold transition shadow-sm cursor-pointer"
                      >
                        <Square className="w-3.5 h-3.5" />
                        Hang Up Simulated Call
                      </button>
                    )}
                  </div>
                </div>

                <div className="text-[10px] text-[var(--color-sentinel-text-dim)] flex items-center justify-between pt-1.5 border-t border-[var(--color-sentinel-border-subtle)]">
                  <span>Channel: PJSIP / Stasis(voiceguard_app)</span>
                  <span className="font-mono text-cyan-400">RTP Forking</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Channel Specs Footer */}
        <div className="pt-3 mt-3 border-t border-[var(--color-sentinel-border-subtle)] flex items-center justify-between text-[11px]">
          <span className="text-[var(--color-sentinel-text-dim)]">Telephony Pipeline:</span>
          <span className="font-mono font-semibold text-cyan-400">Asterisk ARI · 16kHz PCM</span>
        </div>
      </div>
    </div>
  );
};

export default LiveCallIntelligenceStudio;
