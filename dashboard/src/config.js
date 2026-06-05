// src/config.js
// Dynamic environment configuration for REST and WebSocket APIs

export const getApiBase = () => {
  const hostname = window.location.hostname || 'localhost';
  const port = window.location.port;
  
  // If we are developing locally using Vite (port 5173), direct API requests to port 8000.
  // Otherwise, use the page's current origin (e.g. 127.0.0.1:8000 or production domain).
  if (port === '5173') {
    return 'http://' + hostname + ':8000';
  }
  return window.location.origin;
};

export const getWsBase = () => {
  const hostname = window.location.hostname || 'localhost';
  const port = window.location.port;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  
  if (port === '5173') {
    return 'ws://' + hostname + ':8000/ws/live';
  }
  return protocol + '//' + window.location.host + '/ws/live';
};
