// src/hooks/useApi.js
// REST fetcher — skips requests if no token, delegates 401 to AuthContext
import { useState, useEffect } from 'react';
import { getApiBase } from '../config';
import { useAuth } from '../context/AuthContext';

export function useApi(path, intervalMs = 10000, token) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const { kickToLogin } = useAuth();

  useEffect(() => {
    // Don't fire requests without a token — avoids 401 storms
    if (!token) {
      setLoading(false);
      return;
    }

    let active = true;
    const doFetch = async () => {
      try {
        const base = getApiBase();
        const res  = await fetch(`${base}${path}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.status === 401) {
          kickToLogin(token);
          return;
        }
        const json = await res.json();
        if (active) { setData(json); setLoading(false); setError(null); }
      } catch (e) {
        if (active) { setError(e.message); setLoading(false); }
      }
    };
    doFetch();
    const id = setInterval(doFetch, intervalMs);
    return () => { active = false; clearInterval(id); };
  }, [path, intervalMs, token, kickToLogin]);

  return { data, loading, error };
}
