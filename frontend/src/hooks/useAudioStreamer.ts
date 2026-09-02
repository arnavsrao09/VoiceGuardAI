import { useState, useEffect, useRef, useCallback } from 'react';

export interface ModelDetail {
  aasist_score: number | null;
  xlsr_score: number | null;
  prosody: {
    f0_mean: number;
    f0_std: number;
    jitter: number;
    shimmer: number;
    hnr: number;
    spectral_flatness: number;
    prosody_anomaly_score: number;
  };
  speaker_verified: boolean;
}

export interface ComponentScores {
  deepfake: number;
  speaker_match: number;
  speaker_drift: number;
  prosody: number;
  context: number;
}

export interface LiveRiskData {
  score: number;
  level: string;
  chunk_index: number;
  should_alert: boolean;
  alert_reason: string | null;
  raw_components: ComponentScores;
  session_id: string;
  timestamp: string;
  latency_ms: number;
  speech_probability: number;
  model_detail: ModelDetail;
}

export interface LiveAlert {
  id: string;
  sev: 'low' | 'medium' | 'high' | 'critical';
  msg: string;
  time: string;
  session: string;
}

export function useAudioStreamer() {
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [riskData, setRiskData] = useState<LiveRiskData | null>(null);
  const [riskHistory, setRiskHistory] = useState<{ time: string; score: number }[]>([]);
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const [recordingTime, setRecordingTime] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const timerRef = useRef<number | null>(null);

  const stopMonitoring = useCallback(() => {
    setIsMonitoring(false);
    setIsConnected(false);

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const startMonitoring = useCallback(async (file?: File) => {
    setError(null);
    setRecordingTime(0);

    try {
      // 1. Establish WebSocket connection to backend
      const wsUrl = 'ws://localhost:8000/ws/stream';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log('[AudioStreamer] Connected to VoiceGuardAI WebSocket');
      };

      ws.onmessage = (event) => {
        try {
          const data: LiveRiskData = JSON.parse(event.data);
          setRiskData(data);

          // Append to timeline
          const timeLabel = new Date(data.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          });
          setRiskHistory((prev) => [...prev.slice(-29), { time: timeLabel, score: data.score }]);

          // Check for alert
          if (data.should_alert && data.alert_reason) {
            const sev = data.level.toLowerCase() as 'low' | 'medium' | 'high' | 'critical';
            const newAlert: LiveAlert = {
              id: `${data.session_id}-${data.chunk_index}`,
              sev,
              msg: data.alert_reason,
              time: 'Just now',
              session: `#${data.session_id.slice(0, 5)}`,
            };
            setAlerts((prev) => [newAlert, ...prev.slice(0, 19)]);
          }
        } catch (err) {
          console.error('[AudioStreamer] Failed to parse websocket message:', err);
        }
      };

      ws.onerror = (err) => {
        console.warn('[AudioStreamer] WebSocket error:', err);
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
      };

      // 2. Audio Context setup (16kHz)
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioContextClass({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      let source: MediaStreamAudioSourceNode | AudioBufferSourceNode;

      if (file) {
        // Stream from uploaded file
        const arrayBuffer = await file.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        const bufferSource = audioCtx.createBufferSource();
        bufferSource.buffer = audioBuffer;
        
        // Connect directly to destination so user can hear the playback
        bufferSource.connect(audioCtx.destination);
        
        // Stop automatically when file finishes
        bufferSource.onended = () => {
          stopMonitoring();
        };
        
        source = bufferSource;
        bufferSource.start();
      } else {
        // Request user microphone
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
        mediaStreamRef.current = stream;
        source = audioCtx.createMediaStreamSource(stream);
      }

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        // Convert Float32 [-1, 1] -> Int16 PCM [-32768, 32767]
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        // Send binary PCM frame over WebSocket
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(pcm16.buffer);
        }
      };

      source.connect(processor);
      // Processor must be connected to destination for onaudioprocess to trigger (it outputs silence since we don't write to outputBuffer)
      processor.connect(audioCtx.destination);

      setIsMonitoring(true);

      // Start timer
      timerRef.current = window.setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('[AudioStreamer] Failed to start microphone:', err);
      setError((err as Error).message || 'Microphone access denied or audio device error');
      stopMonitoring();
    }
  }, [stopMonitoring]);

  useEffect(() => {
    return () => {
      stopMonitoring();
    };
  }, [stopMonitoring]);

  return {
    isMonitoring,
    isConnected,
    riskData,
    riskHistory,
    alerts,
    recordingTime,
    error,
    startMonitoring,
    stopMonitoring,
  };
}
