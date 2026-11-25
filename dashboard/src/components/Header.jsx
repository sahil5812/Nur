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

  // Determine state display and styling
  let statusClass = running ? '' : 'stopped';
  let statusText = running ? state : 'Stopped';

  if (running) {
    if (engine?.state === 'LIMIT_REACHED' || engine?.limit_reached) {
      statusClass = 'limit-reached';
      statusText = `Limit Reached (${engine?.reset_time_str ? engine.reset_time_str.split(' ')[0] : 'Midnight'})`;
    } else if (engine?.state === 'COOLDOWN' || (engine?.cooldown_left && engine.cooldown_left > 0)) {
      statusClass = 'cooldown';
      statusText = `Cooldown (${engine?.cooldown_left || 0}s)`;
    } else if (engine?.state === 'DAILY_LOSS_LOCKED') {
      statusClass = 'stopped';
      statusText = 'Loss Locked';
    } else if (engine?.state === 'PROFIT_LOCKED') {
      statusClass = 'limit-reached';
      statusText = 'Target Reached';
    } else if (engine?.state === 'WAITING') {
      statusText = 'Waiting';
    } else if (engine?.state === 'IN_TRADE') {
      statusText = 'In Trade';
    }
  }

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

        <div 
          className={`status-pill ${statusClass}`}
          title={engine?.limit_reached ? `Daily limit reached. Resets at ${engine?.reset_time_str || '12:00 AM IST'}` : undefined}
        >
          <span className="status-dot" />
          <span>{statusText}</span>
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
