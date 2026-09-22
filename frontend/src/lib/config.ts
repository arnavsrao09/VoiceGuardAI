// VoiceGuardAI Application Configuration

const getEnvVar = (key: string, defaultValue: string): string => {
  return (import.meta as any).env?.[key] || defaultValue;
};

// Raw backend URL (supports VITE_BACKEND_URL or VITE_API_URL)
const rawBackendUrl = getEnvVar('VITE_BACKEND_URL', getEnvVar('VITE_API_URL', 'http://localhost:8000'));

// Sanitize base server URL (strips trailing slashes and /api/v1)
export const SERVER_BASE_URL: string = rawBackendUrl
  .replace(/\/api\/v1\/?$/, '')
  .replace(/\/$/, '');

// Base HTTP API URL (e.g., https://your-backend.onrender.com/api/v1)
export const API_BASE_URL: string = `${SERVER_BASE_URL}/api/v1`;

// Compute WebSocket URL from SERVER_BASE_URL or VITE_WS_URL
const computeWsUrl = (): string => {
  const customWs = getEnvVar('VITE_WS_URL', '');
  if (customWs) return customWs;

  if (SERVER_BASE_URL.startsWith('https://')) {
    return SERVER_BASE_URL.replace('https://', 'wss://');
  }
  if (SERVER_BASE_URL.startsWith('http://')) {
    return SERVER_BASE_URL.replace('http://', 'ws://');
  }
  return 'ws://localhost:8000';
};

// Base WebSocket URL (e.g., wss://your-backend.onrender.com)
export const WS_BASE_URL: string = computeWsUrl();
