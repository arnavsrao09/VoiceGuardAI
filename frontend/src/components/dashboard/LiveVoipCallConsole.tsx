import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../../lib/config';
import { motion, AnimatePresence } from 'framer-motion';
import { Phone, MapPin, Wifi, Monitor, Globe, Signal, Fingerprint, ShieldCheck, AlertTriangle } from 'lucide-react';

interface CallerGeoData {
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

interface LiveVoipCallConsoleProps {
  onCallStart?: (geoData: CallerGeoData) => void;
  isMonitoring?: boolean;
}

export const LiveVoipCallConsole: React.FC<LiveVoipCallConsoleProps> = ({
  onCallStart,
  isMonitoring = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [geoData, setGeoData] = useState<CallerGeoData | null>(null);
  const [deviceInfo, setDeviceInfo] = useState<{
    browser: string;
    os: string;
    screen: string;
    audioDevices: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Auto-detect device fingerprint on mount
  useEffect(() => {
    const detectDevice = async () => {
      const ua = navigator.userAgent;
      let browser = 'Unknown';
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

      let audioDevices = 0;
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        audioDevices = devices.filter((d) => d.kind === 'audioinput').length;
      } catch {
        audioDevices = 0;
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


  // Fetch real IP geolocation (or test scenario IP)
  const fetchGeoLocation = useCallback(async (targetIp?: string) => {
    setIsLoading(true);
    setError(null);
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
      setError('Failed to fetch caller metadata. Is the backend running?');
      console.error('[VoIPConsole] Geo fetch error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [onCallStart]);

  const isDomestic = geoData?.threat_flag === 'DOMESTIC';

  return (
    <div className="rounded-2xl border border-[#2a2d3d] bg-[#141622]/90 backdrop-blur-md overflow-hidden mb-5 transition-all duration-300">
      {/* Header Toggle */}
      <button
        onClick={() => {
          if (!isExpanded) fetchGeoLocation();
          setIsExpanded(!isExpanded);
        }}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-[#1a1c2a]/60 transition-all group"
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${isMonitoring ? 'bg-emerald-500/15 text-emerald-400' : 'bg-indigo-500/15 text-indigo-400'} transition-colors`}>
            <Phone className="w-4 h-4" />
          </div>
          <div className="text-left">
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-wider flex items-center gap-2">
              Live Telephony & WebRTC Call Console
              {isMonitoring && (
                <span className="flex items-center gap-1 text-[9px] font-bold text-emerald-400 normal-case tracking-normal">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  LIVE
                </span>
              )}
            </h3>
            <p className="text-[10px] text-gray-500 mt-0.5">
              Real IP geolocation · Device fingerprint · Free WebRTC audio channel (No paid API)
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {geoData && (
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
              isDomestic
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-red-500/10 text-red-400 border border-red-500/20'
            }`}>
              {isDomestic ? '🇮🇳 DOMESTIC' : '⚠️ INTERNATIONAL'}
            </span>
          )}
          <motion.span
            animate={{ rotate: isExpanded ? 180 : 0 }}
            className="text-gray-500 text-xs"
          >
            ▼
          </motion.span>
        </div>
      </button>

      {/* Expanded Details */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 border-t border-[#2a2d3d]/60">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                  <span className="ml-3 text-xs text-gray-400">Fetching real IP geolocation...</span>
                </div>
              ) : error ? (
                <div className="flex items-center gap-3 py-6 px-4 rounded-xl bg-red-500/8 border border-red-500/20 mt-4">
                  <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
                  <p className="text-xs text-red-300">{error}</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                  {/* Caller IP Geolocation Card */}
                  <div className="rounded-xl bg-[#1a1c2a]/70 border border-[#2a2d3d]/50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Globe className="w-4 h-4 text-indigo-400" />
                      <h4 className="text-[11px] font-bold text-gray-300 uppercase tracking-wider">
                        Real IP Geolocation
                      </h4>
                    </div>

                    {geoData ? (
                      <div className="space-y-2">
                        {[
                          { icon: MapPin, label: 'Location', value: `${geoData.city}, ${geoData.region}` },
                          { icon: Globe, label: 'Country', value: `${geoData.country} (${geoData.country_code})` },
                          { icon: Wifi, label: 'ISP / Network', value: geoData.isp },
                          { icon: Signal, label: 'IP Address', value: geoData.ip },
                        ].map((item) => (
                          <div key={item.label} className="flex items-center gap-2.5">
                            <item.icon className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                            <span className="text-[10px] text-gray-400 w-20 shrink-0">{item.label}</span>
                            <span className="text-[11px] font-semibold text-gray-200 truncate">{item.value}</span>
                          </div>
                        ))}

                        {/* Threat Flag Badge */}
                        <div className="flex items-center gap-2 mt-3 pt-2 border-t border-[#2a2d3d]/40">
                          {isDomestic ? (
                            <ShieldCheck className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <AlertTriangle className="w-4 h-4 text-red-400" />
                          )}
                          <span className={`text-[10px] font-bold uppercase ${
                            isDomestic ? 'text-emerald-400' : 'text-red-400'
                          }`}>
                            {geoData.threat_flag.replace('_', ' ')}
                          </span>
                          <span className="text-[9px] text-gray-500">
                            {isDomestic
                              ? 'Origin within India — Standard risk context'
                              : 'International origin — Elevated risk modifier applied (+30%)'
                            }
                          </span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-500 italic">No geolocation data available</p>
                    )}
                  </div>

                  {/* Device Fingerprint Card */}
                  <div className="rounded-xl bg-[#1a1c2a]/70 border border-[#2a2d3d]/50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Fingerprint className="w-4 h-4 text-purple-400" />
                      <h4 className="text-[11px] font-bold text-gray-300 uppercase tracking-wider">
                        Device Fingerprint
                      </h4>
                    </div>

                    {deviceInfo ? (
                      <div className="space-y-2">
                        {[
                          { icon: Monitor, label: 'Browser', value: deviceInfo.browser },
                          { icon: Monitor, label: 'OS Platform', value: deviceInfo.os },
                          { icon: Monitor, label: 'Screen Res.', value: deviceInfo.screen },
                          { icon: Signal, label: 'Audio Inputs', value: `${deviceInfo.audioDevices} mic(s) detected` },
                        ].map((item) => (
                          <div key={item.label} className="flex items-center gap-2.5">
                            <item.icon className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                            <span className="text-[10px] text-gray-400 w-20 shrink-0">{item.label}</span>
                            <span className="text-[11px] font-semibold text-gray-200 truncate">{item.value}</span>
                          </div>
                        ))}

                        <div className="flex items-center gap-2 mt-3 pt-2 border-t border-[#2a2d3d]/40">
                          <ShieldCheck className="w-4 h-4 text-cyan-400" />
                          <span className="text-[10px] font-bold text-cyan-400 uppercase">
                            WebRTC Direct Channel
                          </span>
                          <span className="text-[9px] text-gray-500">
                            100% free · No Twilio subscription needed
                          </span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-500 italic">Detecting device...</p>
                    )}
                  </div>
                </div>
              )}



              {/* Action Footer */}
              {geoData && !isLoading && (
                <div className="mt-4 flex items-center justify-between p-3 rounded-xl bg-[#1a1c2a]/50 border border-[#2a2d3d]/40">
                  <div className="flex items-center gap-2">
                    <Phone className="w-4 h-4 text-indigo-400" />
                    <span className="text-[10px] text-gray-400">
                      Audio will stream at <strong className="text-gray-200">16kHz · Mono PCM</strong> via WebSocket to ML pipeline
                    </span>
                  </div>
                  <button
                    onClick={() => fetchGeoLocation()}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-[10px] font-bold text-indigo-400 hover:bg-indigo-500/25 transition-all"
                  >
                    <Globe className="w-3 h-3" />
                    Refresh Location
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default LiveVoipCallConsole;
