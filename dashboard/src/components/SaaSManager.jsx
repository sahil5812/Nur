// src/components/SaaSManager.jsx
import React, { useState, useEffect } from 'react';
import { useSaaSData } from '../hooks/useSaaSData';
import { getApiBase } from '../config';

export default function SaaSManager({ token }) {
  const { users, activeUser, activeUserId, switchUser, loading, error, refresh } = useSaaSData(token);
  const [riskMultiplier, setRiskMultiplier] = useState(1.0);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);

  // Initialize or update the local input state when activeUser changes
  useEffect(() => {
    if (activeUser) {
      setRiskMultiplier(activeUser.risk_multiplier || 1.0);
    }
  }, [activeUser]);

  const handleUserChange = (e) => {
    const val = parseInt(e.target.value, 10);
    switchUser(val);
  };

  const handleSyncOverrides = async () => {
    if (!activeUserId) return;
    try {
      setSyncing(true);
      setSyncStatus(null);
      
      const token = localStorage.getItem('token');
      const headers = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const base = getApiBase();
      const response = await fetch(`${base}/api/saas/update-config`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          user_id: activeUserId,
          risk_multiplier: parseFloat(riskMultiplier),
        }),
      });

      const resData = await response.json();
      if (resData.status === 'success') {
        setSyncStatus({ type: 'success', msg: 'Configuration synced successfully!' });
        refresh(); // Refresh profiles list to sync changes
      } else {
        throw new Error(resData.message || 'Failed to update config');
      }
    } catch (err) {
      console.error(err);
      setSyncStatus({ type: 'error', msg: err.message || 'Sync failed.' });
    } finally {
      setSyncing(false);
    }
  };

  if (loading && users.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 180 }}>
        <div className="spinner"><span className="spin">⟳</span> Loading SaaS Profiles...</div>
      </div>
    );
  }

  if (error && users.length === 0) {
    return (
      <div className="card" style={{ padding: 20, textAlign: 'center', color: 'var(--red)' }}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Failed to Load SaaS Settings</div>
        <div style={{ fontSize: 13, color: 'var(--text-3)' }}>{error}</div>
      </div>
    );
  }

  return (
    <div className="card" style={{ position: 'relative' }}>
      <div className="section-title" style={{ marginBottom: 16 }}>SaaS Trader Manager</div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* User Selection Dropdown */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)' }}>Select Active Trader Account</label>
          <select 
            value={activeUserId || ''} 
            onChange={handleUserChange}
            style={{
              padding: '10px 12px',
              backgroundColor: 'var(--bg-3)',
              color: 'var(--text-1)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              outline: 'none',
              width: '100%'
            }}
          >
            {users.map(u => (
              <option key={u.user_id} value={u.user_id}>
                {u.name} (MT5: {u.mt5_login})
              </option>
            ))}
          </select>
        </div>

        {activeUser && (
          <div 
            style={{ 
              display: 'grid', 
              gridTemplateColumns: '1fr 1fr', 
              gap: 12, 
              backgroundColor: 'var(--bg-2)', 
              padding: 12, 
              borderRadius: 8,
              border: '1px solid var(--border)'
            }}
          >
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Risk Mode</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-1)', marginTop: 2 }}>
                {activeUser.risk_multiplier.toFixed(2)}x Multiplier
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Execution Mode</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: activeUser.environment_mode === 'LIVE' ? 'var(--green)' : 'var(--text-2)', marginTop: 2 }}>
                {activeUser.environment_mode} TRADING
              </div>
            </div>
          </div>
        )}

        {/* Configuration Overrides */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 4 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)' }}>Override Risk Multiplier</label>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--green)' }}>{parseFloat(riskMultiplier).toFixed(2)}x</span>
            </div>
            <input 
              type="range" 
              min="0.1" 
              max="5.0" 
              step="0.1"
              value={riskMultiplier} 
              onChange={(e) => setRiskMultiplier(e.target.value)}
              style={{
                width: '100%',
                cursor: 'pointer',
                accentColor: 'var(--green)',
                height: 6,
                borderRadius: 3,
                backgroundColor: 'var(--border)'
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-3)' }}>
              <span>0.10x (Conservative)</span>
              <span>1.00x (Standard)</span>
              <span>5.00x (Aggressive)</span>
            </div>
          </div>

          {/* Sync Button */}
          <button
            onClick={handleSyncOverrides}
            disabled={syncing || !activeUserId}
            style={{
              padding: '11px',
              backgroundColor: syncing ? 'var(--border)' : 'var(--green)',
              color: '#0a0d14',
              border: 'none',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 700,
              cursor: syncing ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              outline: 'none',
              marginTop: 4,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8
            }}
          >
            {syncing ? (
              <>
                <span className="spin" style={{ display: 'inline-block' }}>⟳</span>
                Syncing Parameters...
              </>
            ) : (
              'Sync Config Overrides'
            )}
          </button>

          {/* Status Message */}
          {syncStatus && (
            <div 
              style={{ 
                padding: '8px 12px', 
                borderRadius: 6, 
                fontSize: 12, 
                fontWeight: 600,
                textAlign: 'center',
                backgroundColor: syncStatus.type === 'success' ? 'rgba(46, 204, 113, 0.1)' : 'rgba(231, 76, 60, 0.1)',
                color: syncStatus.type === 'success' ? 'var(--green)' : 'var(--red)',
                border: `1px solid ${syncStatus.type === 'success' ? 'rgba(46, 204, 113, 0.2)' : 'rgba(231, 76, 60, 0.2)'}`
              }}
            >
              {syncStatus.msg}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
