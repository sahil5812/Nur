// src/components/AccountSwitcher.jsx — Discrete Profile Manager
import React from 'react';

export default function AccountSwitcher({
  accounts,
  activeEmail,
  onSwitch,
  onAdd,
  onRemove,
  onSignOut,
  onSignOutAll
}) {
  const activeAccount = accounts.find(acc => acc.email === activeEmail);
  const otherAccounts = accounts.filter(acc => acc.email !== activeEmail);

  const getInitials = (name) => {
    if (!name) return 'TR';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className="account-switcher-dropdown" onClick={(e) => e.stopPropagation()}>
      
      {/* ── Active Account Profile Card ── */}
      {activeAccount && (
        <div className="switcher-header">
          <div className="switcher-avatar">
            {getInitials(activeAccount.display_name)}
          </div>
          <div className="switcher-user-info">
            <div className="switcher-name">
              {activeAccount.display_name}
            </div>
            <div className="switcher-email" title={activeAccount.email}>
              {activeAccount.email}
            </div>
            {activeAccount.mt5_login && (
              <div className="switcher-mt5">
                <span className="switcher-mt5-indicator" />
                MT5 #{activeAccount.mt5_login}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Saved / Alternate Accounts ── */}
      {otherAccounts.length > 0 && (
        <>
          <div className="switcher-section-title">Switch Account</div>
          <div className="switcher-accounts-list">
            {otherAccounts.map((acc) => (
              <div 
                key={acc.email} 
                className="switcher-account-item"
                onClick={() => onSwitch(acc.email)}
                title={`Switch to ${acc.display_name}`}
              >
                <div className="switcher-account-avatar">
                  {getInitials(acc.display_name)}
                </div>
                <div className="switcher-account-details">
                  <div className="switcher-account-name">
                    {acc.display_name}
                  </div>
                  <div className="switcher-account-email">{acc.email}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="switcher-divider" />
        </>
      )}

      {/* ── Action Buttons with Clean SVG Icons ── */}
      <div 
        className="switcher-action-item"
        onClick={onAdd}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="8.5" cy="7" r="4" />
          <line x1="20" y1="8" x2="20" y2="14" />
          <line x1="23" y1="11" x2="17" y2="11" />
        </svg>
        <span>Add another account</span>
      </div>
      
      <div className="switcher-divider" />
      
      <div 
        className="switcher-action-item"
        onClick={onSignOut}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
        <span>Sign out</span>
      </div>

      <div 
        className="switcher-action-item danger"
        onClick={onSignOutAll}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
        <span>Sign out all accounts</span>
      </div>

    </div>
  );
}
