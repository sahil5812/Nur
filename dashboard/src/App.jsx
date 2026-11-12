// src/App.jsx — Institutional Trading Terminal with Routing
import './index.css';
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AuthCallback from './pages/AuthCallback';
import { useLiveData } from './hooks/useLiveData';
import Header from './components/Header';
import MarketRibbon from './components/MarketRibbon';
import MainChartPanel from './components/MainChartPanel';
import AIExecutionDesk from './components/AIExecutionDesk';
import TerminalDock from './components/TerminalDock';
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
      setToastMessage(`Switched to ${active?.display_name}`);
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
      {/* ── Top Header ── */}
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

      {/* ── Institutional Ticker Ribbon ── */}
      <MarketRibbon stats={stats} engine={engine} connected={connected} />

      {/* ── Main Terminal Workspace ── */}
      <main className="main-content">
        <div className="terminal-workspace">
          {/* ── Left Column: Live Chart + Dock ── */}
          <div className="terminal-left-column">
            <MainChartPanel 
              engine={engine} 
              equityData={data?.equity} 
              marketChart={data?.chart} 
              loading={!data} 
            />
            <TerminalDock 
              trades={data?.trades ?? []} 
              analyticsData={data?.analytics} 
              engine={engine} 
              loading={!data} 
            />
          </div>

          {/* ── Right Column: AI Execution Desk ── */}
          <div className="terminal-right-column">
            <AIExecutionDesk 
              token={token} 
              engine={engine} 
              stats={stats} 
            />
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="terminal-footer">
          Nur Institutional Terminal · Precision Algorithmic Engine ·{' '}
          {connected
            ? <span style={{ color: 'var(--green)' }}>Live Gateway</span>
            : <span style={{ color: 'var(--red)' }}>Offline Gateway</span>}
        </div>
      </main>

      {/* ── Toast Feedback ── */}
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}
