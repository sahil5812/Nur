// src/hooks/useLiveData.js
// WebSocket hook — skips connection if no token, delegates auth failures to AuthContext
import { useState, useEffect, useRef } from 'react';
import { getWsBase } from '../config';
import { useAuth } from '../context/AuthContext';

export function useLiveData(token) {
  const [data,      setData]      = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const { kickToLogin } = useAuth();

  useEffect(() => {
    // Don't connect without a token — avoids 4003 storms
    if (!token) return;

    let ws = null;
    let timeoutId = null;
    let isMounted = true;

    function connect() {
      if (!isMounted) return;
      
      const wsBase = getWsBase();
      const url = wsBase + `?token=${encodeURIComponent(token)}`;
      ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isMounted) setConnected(true);
      };
      
      ws.onclose = (e) => {
        if (isMounted) {
          setConnected(false);
          if (e.code === 4003) {
            kickToLogin(token);
          } else {
            timeoutId = setTimeout(connect, 3000);
          }
        }
      };
      
      ws.onerror = () => {
        ws.close();
      };
      
      ws.onmessage = (e) => {
        if (!isMounted) return;
        try { setData(JSON.parse(e.data)); } catch (_) {}
      };
    }
    
    connect();
    
    return () => {
      isMounted = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [token, kickToLogin]);

  return { data, connected };
}
