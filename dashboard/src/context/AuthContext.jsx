// src/context/AuthContext.jsx
// Centralized auth state — prevents redirect storms from multiple hooks
import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { getActiveAccount, invalidateTokenByValue } from '../utils/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isKicked, setIsKicked] = useState(false);
  const kickedRef = useRef(false);   // ref for non-React callers (WebSocket)

  // Called by any hook that gets a 401 / 4003. Runs ONCE, then ignores.
  const kickToLogin = useCallback((badToken) => {
    if (kickedRef.current) return;     // already redirecting
    kickedRef.current = true;
    invalidateTokenByValue(badToken);
    setIsKicked(true);                 // triggers re-render → PrivateRoute → /login
  }, []);

  return (
    <AuthContext.Provider value={{ isKicked, kickToLogin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
