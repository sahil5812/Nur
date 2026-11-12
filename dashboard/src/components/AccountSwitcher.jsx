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
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className="account-switcher-dropdown">
      
      {/* Active Account Info */}
      {activeAccount && (
        <div className="switcher-header">
          <div className="switcher-avatar">
            {getInitials(activeAccount.display_name)}
          </div>
          <div className="switcher-user-info">
            <div className="switcher-name">
              {activeAccount.display_name}
            </div>
            <div className="switcher-email">{activeAccount.email}</div>
            {activeAccount.mt5_login && (
              <div className="switcher-mt5">MT5 #{activeAccount.mt5_login}</div>
            )}
          </div>
        </div>
      )}

      {/* Alternative accounts list */}
      {otherAccounts.length > 0 && (
        <>
          <div className="switcher-section-title">Saved accounts</div>
          <div className="switcher-accounts-list">
            {otherAccounts.map((acc) => (
              <div 
                key={acc.email} 
                className="switcher-account-item"
                onClick={() => onSwitch(acc.email)}
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

      {/* Actions */}
      <div 
        className="switcher-action-item"
        onClick={onAdd}
      >
        <span>Add another account</span>
      </div>
      
      <div className="switcher-divider" />
      
      <div 
        className="switcher-action-item"
        onClick={onSignOut}
      >
        <span>Sign out</span>
      </div>

      <div 
        className="switcher-action-item"
        onClick={onSignOutAll}
        style={{ color: 'var(--red)' }}
      >
        <span>Sign out all accounts</span>
      </div>

    </div>
  );
}
