// src/components/Header.jsx
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
  const mode    = engine?.market || 'XAUUSD';
  const state   = engine?.state  || '—';

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

  // Extract initials: "Abu Sahil" -> "AS"
  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <header className="header">
      <div className="header-logo">
        <span>NUR</span> Trading Dashboard
      </div>

      <div className="header-right">
        <span style={{ fontSize: 12, color: 'var(--text-2)' }}>
          {mode} · {state}
        </span>

        <div className={`ws-status ${connected ? '' : 'disconnected'}`}>
          <div className="live-dot" />
          {connected ? 'LIVE' : 'OFFLINE'}
        </div>

        <div className={`status-pill ${running ? '' : 'stopped'}`}>
          <span className="status-dot" />
          {running ? 'RUNNING' : 'STOPPED'}
        </div>

        {/* ─── COMPONENT: Interactive Profile Badge & Switcher Dropdown ─── */}
        {activeAccount && (
          <div className="profile-switcher-container" ref={dropdownRef}>
            <div 
              className="profile-badge-btn"
              onClick={() => setSwitcherOpen(!switcherOpen)}
              style={{
                backgroundColor: activeAccount.avatar_color,
                backgroundImage: activeAccount.avatar_url ? `url(${activeAccount.avatar_url})` : 'none'
              }}
              title={`Logged in as ${activeAccount.display_name}`}
            >
              {!activeAccount.avatar_url && getInitials(activeAccount.display_name)}
              <span className="active-dot"></span>
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
