import React, { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '../../lib/config';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Phone,
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
  DollarSign,
  ArrowUpRight,
  ChevronDown,
  ChevronUp,
  Languages,
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

export interface LiveCallIntelligenceHubProps {
  isMonitoring: boolean;
  location?: string;
  amount?: number;
  transferType?: string;
  riskLevel?: string;
  riskScore?: number;
  isExtractedFromSpeech?: boolean;
  onIntentExtracted?: (intent: {
    amount?: number | null;
    channel?: string;
    urgencyLevel?: string;
    summary?: string;
  }) => void;
  onCallStart?: (geoData: CallerGeoData) => void;
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

export const LiveCallIntelligenceHub: React.FC<LiveCallIntelligenceHubProps> = ({
  isMonitoring,
  location = 'Local Network (IN)',
  amount = 50000,
  transferType = 'High-Value Wire Transfer',
  riskLevel = 'LOW',
  riskScore = 0.15,
  isExtractedFromSpeech = false,
  onIntentExtracted,
  onCallStart,
}) => {
  // Navigation & Drawer
  const [activeTab, setActiveTab] = useState<'speech' | 'telephony'>('speech');
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  // Speech-to-text state
  const [transcriptHistory, setTranscriptHistory] = useState<Utterance[]>([]);
  const [interimText, setInterimText] = useState<string>('');
  const [isRecognizing, setIsRecognizing] = useState<boolean>(false);
  const [hasSpeechSupport, setHasSpeechSupport] = useState<boolean>(true);
  const [lastAnalyzedSummary, setLastAnalyzedSummary] = useState<string | null>(null);
  const [sttLang, setSttLang] = useState<string>('en-US'); // Default to English US
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

  const isHighRisk = riskScore >= 0.60;
  const isHighValue = amount >= 25000;

  // Sync refs
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
      console.error('[TelephonyHub] Geo fetch error:', err);
    } finally {
      setIsLoadingGeo(false);
    }
  }, [onCallStart]);

  useEffect(() => {
    fetchGeoLocation();
  }, [fetchGeoLocation]);

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
      console.error('[TelephonyHub] Intent analysis error:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Setup Web Speech Recognition
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

    recognition.onend = () => {
      setIsRecognizing(false);
      if (isMonitoringRef.current) {
        try {
          recognition.start();
        } catch {
          // Ignored
        }
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
      try {
        recognition.stop();
      } catch {
        // Ignored
      }
    };
  }, []);

  // Trigger speech recognition on monitoring toggle
  useEffect(() => {
    if (!recognitionRef.current) return;

    if (isMonitoring) {
      try {
        recognitionRef.current.lang = sttLangRef.current;
        recognitionRef.current.start();
      } catch {
        // Ignored if already started
      }
    } else {
      try {
        recognitionRef.current.stop();
        setInterimText('');
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

  const iconBadgeClass = isMonitoring
    ? 'bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/30'
    : 'bg-[#1a1e2e] text-slate-400';

  return (
    <div className="rounded-2xl border border-[var(--color-sentinel-border)] bg-[#10121b]/95 backdrop-blur-xl overflow-hidden mb-6 shadow-2xl transition-all">
      {/* ── Top Context Summary Strip ── */}
      <div className="px-5 py-3.5 border-b border-[var(--color-sentinel-border)] flex flex-wrap items-center justify-between gap-3 bg-[#151824]/60">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl flex items-center justify-center transition-colors ${iconBadgeClass}`}>
            <Phone className="w-4 h-4" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                Live Telephony & Context Intelligence
              </h3>
              {isMonitoring && (
                <span className="flex items-center gap-1 text-[9px] font-bold text-cyan-400 px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
                  <span className={`w-1.5 h-1.5 rounded-full ${isRecognizing ? 'bg-cyan-400 animate-ping' : 'bg-cyan-400'}`} />
                  {isRecognizing ? 'STT ACTIVE' : 'AUDIO FEED LIVE'}
                </span>
              )}
            </div>
            <p className="text-[10px] text-gray-400 flex items-center gap-1.5 mt-0.5">
              <span>{location}</span>
              <span className="text-gray-600">·</span>
              <span>16kHz Mono PCM</span>
            </p>
          </div>
        </div>

        {/* Dynamic Context Key Metrics */}
        <div className="flex items-center gap-3">
          {lastAnalyzedSummary && (
            <span className="hidden xl:flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-[10px] text-indigo-300 font-medium">
              <Sparkles className="w-3 h-3 text-indigo-400" />
              {lastAnalyzedSummary}
            </span>
          )}

          {/* Target Amount */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#1b1f30] border border-[#2b3048]">
            <DollarSign className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <div>
              <span className="text-[9px] text-gray-400 block leading-tight font-medium">Target Amount</span>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold font-mono text-gray-100 tabular-nums">
                  ${amount.toLocaleString()}
                </span>
                <span className="text-[10px] text-gray-400 font-mono">
                  (₹{(amount * 83).toLocaleString()})
                </span>
              </div>
            </div>
            {isExtractedFromSpeech && (
              <span className="ml-1 flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[9px] font-semibold border border-cyan-500/30" title="Parsed automatically from spoken conversation">
                <Sparkles className="w-2.5 h-2.5" />
                Spoken
              </span>
            )}
          </div>

          {/* Channel */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#1b1f30] border border-[#2b3048]">
            <ArrowUpRight className="w-3.5 h-3.5 text-purple-400 shrink-0" />
            <div>
              <span className="text-[9px] text-gray-400 block leading-tight font-medium">Action Channel</span>
              <span className="text-xs font-semibold text-gray-200 truncate max-w-[140px] block">
                {transferType}
              </span>
            </div>
          </div>

          {/* Risk Modifier Tag */}
          <span className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border ${
            isHighValue || isHighRisk
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/25'
              : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
          }`}>
            {isHighValue ? `Risk Mod (+30%) · ${riskLevel}` : `Context Normal · ${riskLevel}`}
          </span>

          {/* Expand / Collapse */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-[#202538] transition-colors border border-transparent hover:border-[#2f354f]"
            aria-label={isExpanded ? 'Collapse panel' : 'Expand panel'}
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* ── Expandable Body Content ── */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {/* Tab Navigation & Language Switcher */}
            <div className="flex items-center justify-between px-5 py-2.5 border-b border-[var(--color-sentinel-border)] bg-[#121520]">
              <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#1a1e2e] border border-[#282e45]">
                <button
                  onClick={() => setActiveTab('speech')}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                    activeTab === 'speech'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  Live Speech & Intent
                  {transcriptHistory.length > 0 && (
                    <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 text-[9px] flex items-center justify-center font-mono">
                      {transcriptHistory.length}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setActiveTab('telephony')}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                    activeTab === 'telephony'
                      ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-sm'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" />
                  Call Telemetry & Device
                  {geoData && (
                    <span className="text-[10px]">
                      {isDomestic ? '🇮🇳' : '🌐'}
                    </span>
                  )}
                </button>
              </div>

              {/* Right side controls */}
              <div className="flex items-center gap-3">
                {activeTab === 'speech' && (
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 text-xs text-gray-400">
                      <Languages className="w-3.5 h-3.5 text-cyan-400" />
                      <span className="text-[10px] uppercase font-bold text-gray-400">STT Model:</span>
                    </div>
                    <select
                      value={sttLang}
                      onChange={(e) => setSttLang(e.target.value)}
                      className="px-2.5 py-1 rounded-lg bg-[#1a1e2e] border border-[#2b3048] text-xs font-medium text-gray-200 focus:outline-none focus:border-cyan-400 transition-colors"
                    >
                      {SUPPORTED_LANGUAGES.map((lang) => (
                        <option key={lang.code} value={lang.code}>
                          {lang.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {activeTab === 'telephony' && (
                  <button
                    onClick={() => fetchGeoLocation()}
                    disabled={isLoadingGeo}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-[10px] font-bold text-indigo-300 hover:bg-indigo-500/25 transition-all disabled:opacity-50"
                  >
                    <Globe className="w-3 h-3" />
                    {isLoadingGeo ? 'Resolving IP...' : 'Refresh Telemetry'}
                  </button>
                )}
              </div>
            </div>

            {/* Tab 1: Live Speech & Intent Extraction */}
            {activeTab === 'speech' && (
              <div className="p-5 space-y-4">
                {!hasSpeechSupport && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>Browser Web Speech API is not supported in this browser. Please use Chrome, Edge, or Safari, or test using the phrase tester below.</span>
                  </div>
                )}

                {/* Quick-Test Prompts */}
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-cyan-400" />
                    Quick Voice Test Samples:
                  </span>
                  {SAMPLE_PHRASES.map((phrase, idx) => (
                    <button
                      key={idx}
                      onClick={() => processTranscript(phrase)}
                      disabled={isAnalyzing}
                      className="text-[11px] px-2.5 py-1 rounded-lg bg-[#1a1e2e] hover:bg-[#20273d] border border-[#2a3048] hover:border-cyan-500/40 text-slate-200 hover:text-cyan-300 transition-all font-medium disabled:opacity-50"
                    >
                      "{phrase}"
                    </button>
                  ))}
                </div>

                {/* Live Transcript / Utterances Stream */}
                <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
                  {transcriptHistory.length === 0 && !interimText && (
                    <div className="py-6 text-center rounded-xl border border-dashed border-[#282e45] bg-[#141724]/40">
                      <Mic className={`w-5 h-5 mx-auto mb-1.5 ${isMonitoring ? 'text-cyan-400 animate-pulse' : 'text-gray-600'}`} />
                      <p className="text-xs font-semibold text-gray-300">
                        {isMonitoring
                          ? 'Listening to live voice stream... Speak transaction details naturally'
                          : 'Start monitoring or click any sample prompt above to test automated intent extraction.'}
                      </p>
                      <p className="text-[10px] text-gray-500 mt-0.5">
                        Extracts dollar amounts, Indian rupee values, wire requests, and urgent pressure tactics in real time.
                      </p>
                    </div>
                  )}

                  {transcriptHistory.map((item) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="p-3 rounded-xl bg-[#161a28] border border-[#262c42] flex flex-col gap-2"
                    >
                      <div className="flex items-center justify-between text-[10px] text-gray-400">
                        <span className="font-bold text-gray-300 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          {item.sender}
                        </span>
                        <span className="font-mono">{item.timestamp}</span>
                      </div>

                      <p className="text-xs text-gray-200 leading-relaxed font-medium">
                        "{item.text}"
                      </p>

                      {/* Extracted Intent Badges */}
                      {(item.extractedAmount || item.extractedChannel || (item.urgencyCues && item.urgencyCues.length > 0)) && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-[#23283c]">
                          {item.extractedAmount && (
                            <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-[10px] font-bold font-mono">
                              <CheckCircle2 className="w-3 h-3 text-cyan-400" />
                              Detected Amount: ${item.extractedAmount.toLocaleString()}
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
                              Pressure Tactics: {item.urgencyCues?.join(', ')}
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

                {/* Manual Phrase Input Box */}
                <form onSubmit={handleManualSubmit} className="flex items-center gap-2 pt-1">
                  <div className="relative flex-1">
                    <input
                      type="text"
                      value={manualInput}
                      onChange={(e) => setManualInput(e.target.value)}
                      placeholder="Type or paste any spoken caller phrase (e.g. 'I want to transfer 15000 dollars now')..."
                      className="w-full px-3.5 py-2 rounded-xl bg-[#141724] border border-[#282e45] text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-400 transition-colors"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={!manualInput.trim() || isAnalyzing}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-500 text-black text-xs font-bold hover:bg-cyan-400 disabled:opacity-50 transition-all shrink-0 shadow-md"
                  >
                    <Send className="w-3.5 h-3.5" />
                    Analyze Intent
                  </button>
                </form>
              </div>
            )}

            {/* Tab 2: Call Telemetry & Device Specs */}
            {activeTab === 'telephony' && (
              <div className="p-5 space-y-4">
                {geoError ? (
                  <div className="flex items-center gap-3 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                    <span>{geoError}</span>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Geolocation Card */}
                    <div className="p-4 rounded-xl bg-[#161a28] border border-[#262c42] space-y-2.5">
                      <div className="flex items-center justify-between pb-2 border-b border-[#23283c]">
                        <div className="flex items-center gap-2">
                          <Globe className="w-4 h-4 text-indigo-400" />
                          <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                            Origin Geolocation & IP
                          </h4>
                        </div>
                        {geoData && (
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            isDomestic
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-red-500/10 text-red-400 border border-red-500/20'
                          }`}>
                            {geoData.threat_flag}
                          </span>
                        )}
                      </div>

                      {geoData ? (
                        <div className="space-y-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">Resolved City/Region</span>
                            <span className="font-semibold text-gray-200">{geoData.city}, {geoData.region}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">Country</span>
                            <span className="font-semibold text-gray-200">{geoData.country} ({geoData.country_code})</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">ISP / Carrier Network</span>
                            <span className="font-semibold text-gray-200">{geoData.isp}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">IP Address</span>
                            <span className="font-mono font-semibold text-cyan-400">{geoData.ip}</span>
                          </div>
                        </div>
                      ) : (
                        <div className="py-4 text-center text-xs text-gray-500">Resolving geolocation...</div>
                      )}
                    </div>

                    {/* Device & Channel Fingerprint Card */}
                    <div className="p-4 rounded-xl bg-[#161a28] border border-[#262c42] space-y-2.5">
                      <div className="flex items-center justify-between pb-2 border-b border-[#23283c]">
                        <div className="flex items-center gap-2">
                          <Fingerprint className="w-4 h-4 text-purple-400" />
                          <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                            Hardware & Audio Channel
                          </h4>
                        </div>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                          WEBRTC PCM
                        </span>
                      </div>

                      {deviceInfo ? (
                        <div className="space-y-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">Browser & Platform</span>
                            <span className="font-semibold text-gray-200">{deviceInfo.browser} on {deviceInfo.os}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">Screen Resolution</span>
                            <span className="font-mono text-gray-200">{deviceInfo.screen}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">Audio Input Sensors</span>
                            <span className="font-semibold text-gray-200">{deviceInfo.audioDevices} mic input(s)</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-[11px]">WebSocket Stream</span>
                            <span className="font-mono text-emerald-400 font-semibold">16kHz 16-bit Mono</span>
                          </div>
                        </div>
                      ) : (
                        <div className="py-4 text-center text-xs text-gray-500">Detecting hardware specs...</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default LiveCallIntelligenceHub;
