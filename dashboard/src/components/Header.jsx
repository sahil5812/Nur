// src/components/Header.jsx — Institutional Trading Terminal Header
import React, { useRef, useEffect } from 'react';
import AccountSwitcher from './AccountSwitcher';

export default function Header({
  connected,
  engine,
  accounts,
  activeEmail,
  switcherOpen,
  setSwitcherOpen,
  onSwitch,
  onAdd,
  onRemove,
  onSignOut,
  onSignOutAll
}) {
  const running = engine?.state !== undefined;
  const spotPrice = engine?.last_close ? Number(engine.last_close).toFixed(2) : '4050.20';
  const spread = engine?.spread !== undefined ? Number(engine.spread).toFixed(2) : '0.20';
  const state = engine?.state || 'Running';

  const activeAccount = accounts.find(acc => acc.email === activeEmail);
  const dropdownRef = useRef(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setSwitcherOpen(false);
      }
    }
    if (switcherOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [switcherOpen, setSwitcherOpen]);

  const getInitials = (name) => {
    if (!name) return 'TR';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <header className="header">
      {/* ── Left: Brand & Instrument Ticker ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div className="header-logo">
          <span>Nur</span> Terminal
        </div>

        <div className="instrument-ticker-badge">
          <span className="inst-symbol">XAU/USD</span>
          <span className="inst-name">Gold Spot</span>
          <span className="inst-price mono">${spotPrice}</span>
          <span className="inst-spread mono">Spr {spread}</span>
        </div>
      </div>

      {/* ── Center: Session & Protocol Telemetry ── */}
      <div className="header-center-info">
        <span className="session-tag">London / NY Overlap</span>
        <span className="engine-mode-tag mono">M1 Scalp · 200 EMA</span>
      </div>

      {/* ── Right: Status & Account Controls ── */}
      <div className="header-right">
        <div className={`ws-status ${connected ? '' : 'disconnected'}`}>
          <div className="live-dot" />
          <span>{connected ? 'Live' : 'Offline'}</span>
        </div>

        <div className={`status-pill ${running ? '' : 'stopped'}`}>
          <span className="status-dot" />
          <span>{running ? state : 'Stopped'}</span>
        </div>

        {activeAccount && (
          <div className="profile-switcher-container" ref={dropdownRef}>
            <div 
              className="profile-badge-btn"
              onClick={() => setSwitcherOpen(!switcherOpen)}
              title={`Logged in as ${activeAccount.display_name}`}
            >
              {getInitials(activeAccount.display_name)}
              <span className="active-dot" />
            </div>

            {switcherOpen && (
              <AccountSwitcher 
                accounts={accounts}
                activeEmail={activeEmail}
                onSwitch={onSwitch}
                onAdd={onAdd}
                onRemove={onRemove}
                onSignOut={onSignOut}
                onSignOutAll={onSignOutAll}
              />
            )}
          </div>
        )}
      </div>
    </header>
  );
}
