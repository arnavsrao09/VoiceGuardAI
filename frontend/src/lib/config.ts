// VoiceGuardAI Application Configuration

const getEnvVar = (key: string, defaultValue: string): string => {
  return (import.meta as any).env?.[key] || defaultValue;
};

// Base HTTP API URL (default: http://localhost:8000/api/v1)
export const API_BASE_URL: string = getEnvVar('VITE_API_URL', 'http://localhost:8000/api/v1');

// Base WebSocket URL (default: ws://localhost:8000)
export const WS_BASE_URL: string = getEnvVar('VITE_WS_URL', 'ws://localhost:8000');

// Base HTTP Server URL without path (default: http://localhost:8000)
export const SERVER_BASE_URL: string = API_BASE_URL.replace(/\/api\/v1\/?$/, '');
