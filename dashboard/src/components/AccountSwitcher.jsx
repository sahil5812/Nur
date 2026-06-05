// src/components/AccountSwitcher.jsx
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

  // Get initials: "Abu Sahil" -> "AS"
  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className="account-switcher-dropdown">
      
      {/* Active Account Info Header */}
      {activeAccount && (
        <div className="switcher-header">
          <div 
            className="switcher-avatar"
            style={{ 
              backgroundColor: activeAccount.avatar_color,
              backgroundImage: activeAccount.avatar_url ? `url(${activeAccount.avatar_url})` : 'none'
            }}
          >
            {!activeAccount.avatar_url && getInitials(activeAccount.display_name)}
          </div>
          <div className="switcher-user-info">
            <div className="switcher-name">
              {activeAccount.display_name} <span style={{ color: 'var(--green)', fontSize: 10 }}>●</span>
            </div>
            <div className="switcher-email">{activeAccount.email}</div>
            {activeAccount.mt5_login && (
              <div className="switcher-mt5">MT5 ID: {activeAccount.mt5_login}</div>
            )}
          </div>
        </div>
      )}

      {/* Alternative saved profiles list */}
      {otherAccounts.length > 0 && (
        <>
          <div className="switcher-section-title">Switch Account</div>
          <div className="switcher-accounts-list">
            {otherAccounts.map((acc) => (
              <div 
                key={acc.email} 
                className="switcher-account-item"
                onClick={() => onSwitch(acc.email)}
              >
                <div 
                  className="switcher-account-avatar"
                  style={{ 
                    backgroundColor: acc.avatar_color,
                    backgroundImage: acc.avatar_url ? `url(${acc.avatar_url})` : 'none'
                  }}
                >
                  {!acc.avatar_url && getInitials(acc.display_name)}
                </div>
                <div className="switcher-account-details">
                  <div className="switcher-account-name">
                    {acc.display_name} <span style={{ color: 'var(--text-3)', fontSize: 9 }}>●</span>
                  </div>
                  <div className="switcher-account-email">{acc.email}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="switcher-divider"></div>
        </>
      )}

      {/* Actions */}
      <div 
        className="switcher-action-item"
        onClick={onAdd}
      >
        <span style={{ fontSize: 14 }}>＋</span> Add another account
      </div>
      
      <div className="switcher-divider"></div>
      
      <div 
        className="switcher-action-item"
        onClick={onSignOut}
        style={{ color: 'rgba(239, 68, 68, 0.85)' }}
      >
        🚪 Sign out (this account)
      </div>

      <div 
        className="switcher-action-item"
        onClick={onSignOutAll}
        style={{ color: 'var(--red)' }}
      >
        🚪 Sign out (all accounts)
      </div>

    </div>
  );
}
