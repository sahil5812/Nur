// src/components/ForceTradeModal.jsx
import React, { useState, useEffect } from 'react';
import { useSaaSData } from '../hooks/useSaaSData';
import { useLiveData } from '../hooks/useLiveData';
import { getApiBase } from '../config';

export default function ForceTradeModal({ token }) {
  const { activeUser, activeUserId, refresh } = useSaaSData(token);
  const { data: liveData } = useLiveData(token);
  
  // State variables
  const [modalOpen, setModalOpen] = useState(false);
  const [direction, setDirection] = useState('BUY');
  const [riskFactor, setRiskFactor] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [openPositions, setOpenPositions] = useState([]);
  
  // Toast notifications
  const [toastOpen, setToastOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastSeverity, setToastSeverity] = useState('success');

  // Fetch open positions for active user
  const fetchOpenPositions = async () => {
    if (!activeUserId) return;
    try {
      const token = localStorage.getItem('token');
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const base = getApiBase();
      const response = await fetch(`${base}/api/open_positions?user_id=${activeUserId}`, { headers });
      if (response.ok) {
        const list = await response.json();
        setOpenPositions(list);
      }
    } catch (err) {
      console.error("Failed to fetch open positions:", err);
    }
  };

  // Poll open positions every 2 seconds
  useEffect(() => {
    fetchOpenPositions();
    const interval = setInterval(fetchOpenPositions, 2000);
    return () => clearInterval(interval);
  }, [activeUserId]);

  // Auto-dismiss toast notification after 5 seconds
  useEffect(() => {
    if (toastOpen) {
      const timer = setTimeout(() => {
        setToastOpen(false);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [toastOpen]);

  const currentPrice = liveData?.engine?.last_close || 0;
  const balance = liveData?.stats?.balance || 10000.0;

  // Calculate estimated lot size matching backend calculations
  const calculateEstimatedLot = () => {
    const riskPercent = 2.0; // default RISK_PERCENT
    const slAtrMult = 1.5;
    const atr = 2.0; // fallback standard ATR
    
    const riskAmount = balance * (riskPercent / 100.0) * riskFactor;
    const slDistance = atr * slAtrMult;
    const baseLot = riskAmount / (slDistance * 100.0);
    const estimatedLot = Math.round(Math.max(baseLot * 1.5, 0.01) * 100) / 100;
    return estimatedLot.toFixed(2);
  };

  // Handle Risk slider description
  const getRiskWarning = () => {
    if (riskFactor <= 0.5) return { text: "Conservative (Safe)", color: "var(--green)" };
    if (riskFactor <= 2.0) return { text: "Balanced (Normal)", color: "var(--accent)" };
    return { text: "Aggressive (High Risk) 🚨", color: "var(--red)" };
  };

  const riskInfo = getRiskWarning();

  // Trigger Confirmation Modal
  const handleOpenModal = (dir) => {
    setDirection(dir);
    setModalOpen(true);
  };

  // Execute Force Trade API Call
  const handleExecuteTrade = async () => {
    if (!activeUserId) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const base = getApiBase();
      // Step 1: Temporarily update the risk_multiplier config on backend
      await fetch(`${base}/api/saas/update-config`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          user_id: activeUserId,
          risk_multiplier: parseFloat(riskFactor),
        }),
      });

      // Step 2: Post the manual trade override command
      const response = await fetch(`${base}/api/force_trade`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          tenant_id: String(activeUserId),
          direction: direction,
          reason: `Manual Override (${riskFactor}x Risk)`,
        }),
      });

      const res = await response.json();
      if (res.id) {
        setToastSeverity('success');
        setToastMessage(`✓ Trade executed. Agent is now TRAILING...`);
        setToastOpen(true);
        setModalOpen(false);
        fetchOpenPositions();
        refresh(); // refresh global settings UI

        // Poll for execution confirmation (check every 500ms, max 5 times)
        const previousTradeCount = liveData?.stats?.total_trades || 0;
        let attempts = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const base = getApiBase();
            const statsRes = await fetch(`${base}/api/stats`, {
              headers: { Authorization: `Bearer ${token}` }
            });
            if (statsRes.ok) {
              const stats = await statsRes.json();
              if (stats.total_trades > previousTradeCount) {
                clearInterval(pollInterval);
                fetchOpenPositions();
              }
            }
          } catch (e) {
            console.error("Polling stats failed:", e);
          }
          if (attempts >= 5) {
            clearInterval(pollInterval);
            fetchOpenPositions(); // Final fallback check
          }
        }, 500);
      } else {
        throw new Error(res.error || 'Failed to execute override');
      }
    } catch (err) {
      console.error(err);
      setToastSeverity('error');
      setToastMessage(`Error executing manual trade: ${err.message}`);
      setToastOpen(true);
    } finally {
      setLoading(false);
    }
  };

  // Execute Close All API Call
  const handleCloseAll = async () => {
    if (!activeUserId) return;
    if (!confirm("Are you sure you want to close ALL positions?")) return;
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const base = getApiBase();
      const response = await fetch(`${base}/api/force_close`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          tenant_id: String(activeUserId),
        }),
      });
      const res = await response.json();
      setToastSeverity('info');
      setToastMessage(`Closed positions: ${res.closed_positions || 0} | P&L: $${(res.total_pnl || 0).toFixed(2)}`);
      setToastOpen(true);
      fetchOpenPositions();
    } catch (err) {
      console.error(err);
      setToastSeverity('error');
      setToastMessage(`Failed to close positions: ${err.message}`);
      setToastOpen(true);
    }
  };

  // Close specific position
  const handleCloseTicket = async (ticket) => {
    if (!activeUserId) return;
    try {
      const token = localStorage.getItem('token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const base = getApiBase();
      const response = await fetch(`${base}/api/force_close`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          tenant_id: String(activeUserId),
          ticket: Number(ticket)
        }),
      });
      const res = await response.json();
      setToastSeverity('info');
      setToastMessage(`Position closure command queued`);
      setToastOpen(true);
      fetchOpenPositions();
    } catch (err) {
      console.error(err);
      setToastSeverity('error');
      setToastMessage(`Failed to close position: ${err.message}`);
      setToastOpen(true);
    }
  };

  // Trailing stops are active if there's an open manual trade
  const isAgentTrailing = openPositions.some(p => p.magic === 999999 || p.comment === "NUR BOT v2");

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      
      {/* ─── AGENT STATE BANNER ─── */}
      {isAgentTrailing && (
        <div style={{
          backgroundColor: 'rgba(245, 158, 11, 0.12)',
          border: '1px solid var(--yellow)',
          color: 'var(--yellow)',
          padding: '10px 14px',
          borderRadius: 8,
          fontSize: 12,
          fontWeight: 700,
          textAlign: 'center',
          letterSpacing: 0.5
        }}>
          ⚠️ Agent Mode: MANUAL_TRAILING (Blocking auto-entries)
        </div>
      )}

      {/* ─── COMPONENT: Risk Slider ─── */}
      <div className="card">
        <div className="card-title">Manual Override Risk Controls</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--text-2)' }}>Override Risk Factor:</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: riskInfo.color }}>
              {parseFloat(riskFactor).toFixed(2)}x ({riskInfo.text})
            </span>
          </div>
          
          <input
            type="range"
            min="0.1"
            max="5.0"
            step="0.1"
            value={riskFactor}
            onChange={(e) => setRiskFactor(parseFloat(e.target.value))}
            style={{
              width: '100%',
              cursor: 'pointer',
              accentColor: riskInfo.color,
              height: 6,
              borderRadius: 3,
              backgroundColor: 'var(--bg-card2)',
              outline: 'none'
            }}
          />
          
          <div style={{ fontSize: 11, color: 'var(--text-3)', fontStyle: 'italic' }}>
            Based on risk {parseFloat(riskFactor).toFixed(1)}x and balance ${balance.toLocaleString()}, lot will be: <span className="mono" style={{ color: 'var(--text-1)', fontWeight: 600 }}>{calculateEstimatedLot()}</span>
          </div>
        </div>
      </div>

      {/* ─── COMPONENT: Force Buttons ─── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.2fr', gap: 10 }}>
        <button
          onClick={() => handleOpenModal('BUY')}
          style={{
            padding: '12px 6px',
            backgroundColor: 'var(--green)',
            color: '#0a0d14',
            border: 'none',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 4
          }}
        >
          📈 FORCE BUY
        </button>

        <button
          onClick={() => handleOpenModal('SELL')}
          style={{
            padding: '12px 6px',
            backgroundColor: 'var(--red)',
            color: '#f1f5f9',
            border: 'none',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 4
          }}
        >
          📉 FORCE SELL
        </button>

        <button
          onClick={handleCloseAll}
          style={{
            padding: '12px 6px',
            backgroundColor: '#111827',
            color: 'var(--text-2)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 4,
            transition: 'background-color 0.2s'
          }}
        >
          ❌ CLOSE ALL
        </button>
      </div>

      {/* ─── COMPONENT: Active Positions Panel ─── */}
      {openPositions.length > 0 && (
        <div className="card" style={{ padding: 16 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>Active Positions</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {openPositions.map((pos) => {
              const isWin = pos.profit >= 0;
              const isManual = pos.magic === 999999 || pos.comment === "NUR BOT v2";
              return (
                <div 
                  key={pos.ticket} 
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    backgroundColor: 'var(--bg-card2)',
                    padding: '8px 12px',
                    borderRadius: 6,
                    border: '1px solid var(--border)'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: pos.type === 0 ? 'var(--green)' : 'var(--red)' }}>
                        {pos.type === 0 ? 'BUY' : 'SELL'}
                      </span>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>#{pos.ticket}</span>
                      <span style={{
                        fontSize: 9, fontWeight: 700, padding: '2px 4px', borderRadius: 4,
                        background: isManual ? 'rgba(245, 158, 11, 0.15)' : 'rgba(99,102,241,0.15)',
                        color: isManual ? 'var(--yellow)' : '#818cf8'
                      }}>
                        {isManual ? 'MANUAL' : 'AUTO'}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 2 }}>
                      Entry: <span className="mono">${pos.price_open.toFixed(2)}</span> → Current: <span className="mono">${pos.price_current.toFixed(2)}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: isWin ? 'var(--green)' : 'var(--red)' }}>
                      {isWin ? '+' : ''}${pos.profit.toFixed(2)}
                    </span>
                    <button
                      onClick={() => handleCloseTicket(pos.ticket)}
                      style={{
                        padding: '4px 8px',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        color: 'var(--red)',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                        borderRadius: 4,
                        fontSize: 10,
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      CLOSE
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ─── CONFIRMATION DIALOG (Vanilla HTML overlay) ─── */}
      {modalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              🚨 OVERRIDE ALERT
            </div>
            
            <div className="modal-alert">
              <strong>You are bypassing NUR AI algorithms.</strong>
              <div style={{ marginTop: 4 }}>Manual trades override model directives and can significantly increase risk exposure.</div>
            </div>

            <div className="modal-grid">
              <div className="modal-grid-item">
                <span className="label">Asset</span>
                <span className="value">XAUUSD</span>
              </div>
              <div className="modal-grid-item">
                <span className="label">Direction</span>
                <span className="value" style={{ color: direction === 'BUY' ? 'var(--green)' : 'var(--red)' }}>
                  FORCE {direction}
                </span>
              </div>
              <div className="modal-grid-item">
                <span className="label">Current Price</span>
                <span className="value mono">${currentPrice.toFixed(2)}</span>
              </div>
              <div className="modal-grid-item">
                <span className="label">Est. Lot Size</span>
                <span className="value mono" style={{ color: riskInfo.color }}>
                  {calculateEstimatedLot()}
                </span>
              </div>
            </div>

            <div style={{ fontSize: 11, color: 'var(--text-3)', fontStyle: 'italic', marginBottom: 20 }}>
              Override Configuration: {parseFloat(riskFactor).toFixed(1)}x Risk Factor
            </div>

            <div className="modal-actions">
              <button
                className="btn-cancel"
                onClick={() => setModalOpen(false)}
                disabled={loading}
              >
                Cancel
              </button>
              <button
                className={`btn-confirm ${direction.toLowerCase()}`}
                onClick={handleExecuteTrade}
                disabled={loading}
              >
                {loading ? 'Executing...' : 'Yes, Execute'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── TOAST NOTIFICATIONS (Vanilla HTML) ─── */}
      {toastOpen && (
        <div className={`toast-notification ${toastSeverity}`}>
          <span>{toastMessage}</span>
          <span className="toast-close" onClick={() => setToastOpen(false)}>×</span>
        </div>
      )}

    </div>
  );
}
