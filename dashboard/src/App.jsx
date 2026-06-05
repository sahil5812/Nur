// src/App.jsx — Main App with Routing
import './index.css';
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AuthCallback from './pages/AuthCallback';
import { useLiveData }  from './hooks/useLiveData';
import Header           from './components/Header';
import StatCards        from './components/StatCards';
import EquityChart      from './components/EquityChart';
import EnginePanel      from './components/EnginePanel';
import TradeHistory     from './components/TradeHistory';
import Analytics        from './components/Analytics';
import SaaSManager      from './components/SaaSManager';
import ForceTradeModal  from './components/ForceTradeModal';
import { getActiveAccount, getSavedAccounts, switchAccount, removeAccount, addNewAccount, autoRefreshToken } from './utils/auth';
import { getApiBase } from './config';

// Route Guard — checks both localStorage AND the isKicked flag from AuthContext
function PrivateRoute({ children }) {
  const { isKicked } = useAuth();
  const activeAccount = getActiveAccount();
  return (activeAccount && !isKicked) ? children : <Navigate to="/login" replace />;
}

// Inner Dashboard Component
function DashboardView() {
  const [activeEmail, setActiveEmail] = useState(getActiveAccount()?.email || '');
  const [token, setToken] = useState(getActiveAccount()?.token || '');
  const [accounts, setAccounts] = useState(getSavedAccounts());
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  // WebSocket Live data hook accepts token as dynamic dependency
  const { data, connected } = useLiveData(token);

  const stats  = data?.stats  ?? null;
  const engine = data?.engine ?? null;

  // Auto-refresh token checking loop (once on mount, then hourly)
  useEffect(() => {
    const checkRefresh = async () => {
      const active = getActiveAccount();
      if (active) {
        const newToken = await autoRefreshToken(active);
        if (newToken) {
          setToken(newToken);
          setAccounts(getSavedAccounts());
        }
      }
    };
    checkRefresh();
    const interval = setInterval(checkRefresh, 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleSwitchAccount = (email) => {
    const newToken = switchAccount(email);
    if (newToken) {
      localStorage.setItem('token', newToken);
      
      const active = getActiveAccount();
      setActiveEmail(email);
      setToken(newToken);
      setAccounts(getSavedAccounts());
      setSwitcherOpen(false);
      setToastMessage(`✓ Switched to ${active?.display_name}`);
      setTimeout(() => setToastMessage(''), 4000);
    }
  };

  const handleAddAccount = () => {
    addNewAccount();
    window.location.href = '/login?add_account=true';
  };

  const handleRemoveAccount = (emailToRemove) => {
    const active = removeAccount(emailToRemove);
    const updated = getSavedAccounts();
    setAccounts(updated);
    if (updated.length === 0) {
      localStorage.removeItem('token');
      fetch(`${getApiBase()}/api/auth/logout`, { method: 'POST' }).catch(() => {});
      window.location.href = '/login';
    } else if (active) {
      localStorage.setItem('token', active.token);
      setActiveEmail(active.email);
      setToken(active.token);
    }
  };

  const handleSignOut = () => {
    const active = getActiveAccount();
    if (active) {
      handleRemoveAccount(active.email);
    }
  };

  const handleSignOutAll = () => {
    localStorage.removeItem('nur_accounts');
    localStorage.removeItem('token');
    fetch(`${getApiBase()}/api/auth/logout`, { method: 'POST' }).catch(() => {});
    window.location.href = '/login';
  };

  return (
    <div className="layout">
      <Header 
        connected={connected} 
        engine={engine} 
        accounts={accounts}
        activeEmail={activeEmail}
        switcherOpen={switcherOpen}
        setSwitcherOpen={setSwitcherOpen}
        onSwitch={handleSwitchAccount}
        onAdd={handleAddAccount}
        onRemove={handleRemoveAccount}
        onSignOut={handleSignOut}
        onSignOutAll={handleSignOutAll}
      />

      <main className="main-content">
        {/* ── Row 1: KPI Cards ─────────────────────── */}
        <StatCards stats={stats} />

        {/* ── Row 2: Equity + Engine Status ────────── */}
        <div className="grid-2">
          <EquityChart equityData={data?.equity} loading={!data} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <EnginePanel engine={engine} stats={stats} />
            <SaaSManager token={token} />
            <ForceTradeModal token={token} />
          </div>
        </div>

        {/* ── Row 3: Trade History ──────────────────── */}
        <TradeHistory trades={data?.trades ?? []} total={stats?.total_trades ?? 0} loading={!data} />

        {/* ── Row 4: Analytics ─────────────────────── */}
        <Analytics analyticsData={data?.analytics} loading={!data} />

        {/* ── Footer ───────────────────────────────── */}
        <div style={{ textAlign: 'center', color: 'var(--text-3)', fontSize: 11, padding: '8px 0' }}>
          Nur Trading Bot · Dashboard v3.0 ·{' '}
          {connected
            ? <span style={{ color: 'var(--green)' }}>Live ●</span>
            : <span style={{ color: 'var(--red)' }}>Offline ●</span>}
        </div>
      </main>

      {/* ─── TOAST NOTIFICATIONS ─── */}
      {toastMessage && (
        <div className="toast-notification info">
          <span>{toastMessage}</span>
          <span className="toast-close" onClick={() => setToastMessage('')}>×</span>
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route 
            path="/" 
            element={
              <PrivateRoute>
                <DashboardView />
              </PrivateRoute>
            } 
          />
          {/* Fallback redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}
