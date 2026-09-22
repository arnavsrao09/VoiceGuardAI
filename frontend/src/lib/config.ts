// VoiceGuardAI Application Configuration

const getEnvVar = (key: string, defaultValue: string): string => {
  return (import.meta as any).env?.[key] || defaultValue;
};

// Base HTTP API URL (default: http://localhost:8000/api/v1)
export const API_BASE_URL: string = getEnvVar('VITE_API_URL', 'http://localhost:8000/api/v1');

// Dynamic fallback for WebSocket based on current protocol and host
const getDefaultWsUrl = (): string => {
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${window.location.host}`;
  }
  return 'ws://localhost:8000';
};

// Base WebSocket URL
export const WS_BASE_URL: string = getEnvVar('VITE_WS_URL', getDefaultWsUrl());

// Base HTTP Server URL without path
export const SERVER_BASE_URL: string = API_BASE_URL.replace(/\/api\/v1\/?$/, '');
