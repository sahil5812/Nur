// src/components/AIDecisionPanel.jsx — Institutional AI Decision & Risk Controller
import React, { useState, useEffect, useMemo } from 'react';
import { getApiBase } from '../config';

export default function AIDecisionPanel({ token, engine, stats }) {
  const [rfMeta, setRfMeta] = useState(null);
  const [showFeatures, setShowFeatures] = useState(false);
  const [riskFactor, setRiskFactor] = useState(1.0);
  const [openPositions, setOpenPositions] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [toast, setToast] = useState(null);

  // Fetch RF Meta info on mount
  useEffect(() => {
    const fetchRfMeta = async () => {
      try {
        const base = getApiBase();
        const res = await fetch(`${base}/api/rf_model`);
        if (res.ok) {
          const data = await res.json();
          setRfMeta(data);
        }
      } catch (e) {
        console.error("Failed to fetch RF meta:", e);
      }
    };
    fetchRfMeta();
  }, []);

  // Fetch open positions periodically
  const fetchOpenPositions = async () => {
    try {
      const base = getApiBase();
      const headers = {};
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      const res = await fetch(`${base}/api/open_positions`, { headers });
      if (res.ok) {
        const data = await res.json();
        setOpenPositions(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error("Failed to fetch open positions:", e);
    }
  };

  useEffect(() => {
    fetchOpenPositions();
    const interval = setInterval(fetchOpenPositions, 1500);
    return () => clearInterval(interval);
  }, [token]);

  // Auto clear toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Sync risk multiplier to backend
  const updateRisk = async (newVal) => {
    const val = parseFloat(newVal);
    setRiskFactor(val);
    try {
      const base = getApiBase();
      const headers = { 'Content-Type': 'application/json' };
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      await fetch(`${base}/api/risk_config`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ risk_multiplier: val })
      });
    } catch (e) {
      console.error("Failed to sync risk:", e);
    }
  };

  // Dynamic Lot Size Calculation
  const balance = stats?.balance || 100000.0;
  const atr = engine?.atr || 2.0;
  const estimatedLot = useMemo(() => {
    const riskPercent = 2.0;
    const slAtrMult = 1.5;
    const riskAmount = balance * (riskPercent / 100.0) * riskFactor;
    const slDistance = Math.max(atr * slAtrMult, 1.0);
    const baseLot = riskAmount / (slDistance * 100.0);
    const lot = Math.round(Math.max(baseLot * 1.5, 0.01) * 100) / 100;
    return lot.toFixed(2);
  }, [balance, atr, riskFactor]);

  // Live indicators and RF values
  const rfProbRaw = engine?.rf_prob !== undefined ? engine.rf_prob : 0.584;
  const rfProbPct = (rfProbRaw * 100).toFixed(1);
  const minThreshold = (rfMeta?.min_threshold || 0.54) * 100;
  const isApproved = engine?.rf_approved !== undefined ? engine.rf_approved : (rfProbRaw >= 0.54);

  const h4Bias = engine?.h4_bias || 'BULLISH';
  const h1Trend = engine?.h1_trend || engine?.trend || 'BULLISH';
  const zM1 = engine?.z_m1 !== undefined ? (engine.z_m1 > 0 ? `+${engine.z_m1}σ` : `${engine.z_m1}σ`) : '+0.34σ';
  const regime = engine?.regime || 'TRENDING';

  // Fast Trade Trigger
  const handleFastTrade = async (direction) => {
    setActionLoading(true);
    try {
      const base = getApiBase();
      const headers = { 'Content-Type': 'application/json' };
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch(`${base}/api/force_trade`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          tenant_id: "1",
          direction: direction,
          reason: `Fast ${direction} via AI Controller (${riskFactor}x Risk)`,
        })
      });

      const data = await res.json();
      if (data.id) {
        setToast({ type: 'success', msg: `Order executed: ${direction} Gold. Automated trailing stop engaged.` });
        fetchOpenPositions();
      } else {
        throw new Error(data.error || 'Execution failed');
      }
    } catch (e) {
      setToast({ type: 'error', msg: `Trade execution failed: ${e.message}` });
    } finally {
      setActionLoading(false);
    }
  };

  // Close All Trigger
  const handleCloseAll = async () => {
    if (!confirm("Confirm closing all open positions at market?")) return;
    setActionLoading(true);
    try {
      const base = getApiBase();
      const headers = { 'Content-Type': 'application/json' };
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch(`${base}/api/force_close`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ tenant_id: "1" })
      });

      const data = await res.json();
      setToast({
        type: 'info',
        msg: `Flattened ${data.closed_positions || 0} position(s) · Realized P&L: $${(data.total_pnl || 0).toFixed(2)}`
      });
      fetchOpenPositions();
    } catch (e) {
      setToast({ type: 'error', msg: `Position liquidation failed: ${e.message}` });
    } finally {
      setActionLoading(false);
    }
  };

  // Close specific position
  const handleCloseTicket = async (ticket) => {
    try {
      const base = getApiBase();
      const headers = { 'Content-Type': 'application/json' };
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      await fetch(`${base}/api/force_close`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ tenant_id: "1", ticket: Number(ticket) })
      });

      setToast({ type: 'info', msg: `Closing order #${ticket}` });
      fetchOpenPositions();
    } catch (e) {
      setToast({ type: 'error', msg: `Close failed: ${e.message}` });
    }
  };

  const isTrailing = openPositions.length > 0;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      
      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
        <div>
          <div className="section-title">AI decision & risk controller</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
            Meta-labeling random forest · 12 pruned features · Regime veto
          </div>
        </div>

        <div>
          {isApproved ? (
            <span style={{
              backgroundColor: 'rgba(76, 195, 138, 0.1)',
              border: '1px solid rgba(76, 195, 138, 0.25)',
              color: 'var(--green)',
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              fontSize: 11,
              fontWeight: 500,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6
            }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'var(--green)' }} />
              Approved (P ≥ {minThreshold.toFixed(0)}%)
            </span>
          ) : (
            <span style={{
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              color: 'var(--yellow)',
              padding: '3px 8px',
              borderRadius: 'var(--radius-sm)',
              fontSize: 11,
              fontWeight: 500,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6
            }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'var(--yellow)' }} />
              Veto active (P &lt; {minThreshold.toFixed(0)}%)
            </span>
          )}
        </div>
      </div>

      {/* ── Toast Notification ── */}
      {toast && (
        <div style={{
          padding: '8px 12px',
          borderRadius: 'var(--radius-sm)',
          fontSize: 11,
          fontWeight: 500,
          backgroundColor: toast.type === 'error' ? 'rgba(229, 72, 77, 0.1)' : (toast.type === 'info' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(76, 195, 138, 0.1)'),
          border: `1px solid ${toast.type === 'error' ? 'rgba(229, 72, 77, 0.25)' : (toast.type === 'info' ? 'rgba(59, 130, 246, 0.25)' : 'rgba(76, 195, 138, 0.25)')}`,
          color: toast.type === 'error' ? 'var(--red)' : (toast.type === 'info' ? 'var(--accent)' : 'var(--green)'),
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>{toast.msg}</span>
          <span style={{ cursor: 'pointer', opacity: 0.6 }} onClick={() => setToast(null)}>×</span>
        </div>
      )}

      {/* ── Section 1: Conviction Gate & Feature Pruning ── */}
      <div style={{ backgroundColor: 'var(--bg-card2)', padding: 12, borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-2)' }}>Win probability confidence</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: isApproved ? 'var(--green)' : 'var(--yellow)' }} className="mono">
            {rfProbPct}%
          </span>
        </div>

        {/* Progress Track */}
        <div style={{ position: 'relative', width: '100%', height: 6, backgroundColor: 'var(--bg-base)', borderRadius: 3, overflow: 'hidden', marginBottom: 6 }}>
          <div style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${Math.min(100, Math.max(0, rfProbRaw * 100))}%`,
            backgroundColor: isApproved ? 'var(--green)' : 'var(--yellow)',
            borderRadius: 3,
            transition: 'width 200ms var(--ease)'
          }} />
          <div style={{
            position: 'absolute',
            left: `${minThreshold}%`,
            top: 0,
            bottom: 0,
            width: 2,
            backgroundColor: 'var(--text-1)',
            opacity: 0.8
          }} title={`Cutoff: ${minThreshold}%`} />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
          <span>Chop floor (0%)</span>
          <span style={{ color: 'var(--text-2)' }}>Veto cutoff: {minThreshold.toFixed(0)}%</span>
          <span>Conviction (100%)</span>
        </div>

        {/* Feature Pruning Toggle */}
        <div style={{ marginTop: 10, borderTop: '1px solid var(--border-subtle)', paddingTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
            Architecture: <span style={{ color: 'var(--text-2)' }}>12 of 17 features active</span>
          </span>
          <button 
            type="button"
            onClick={() => setShowFeatures(!showFeatures)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--accent)',
              fontSize: 11,
              fontWeight: 500,
              cursor: 'pointer',
              padding: 0
            }}
          >
            {showFeatures ? 'Hide weights' : 'Inspect weights'}
          </button>
        </div>

        {showFeatures && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
            {[
              { f: 'z_h1', w: '18.2%' },
              { f: 'z_m5', w: '13.8%' },
              { f: 'z_m1', w: '10.8%' },
              { f: 'realized_vol', w: '9.7%' },
              { f: 'macd_hist', w: '9.7%' },
              { f: 'z_align', w: '8.7%' },
              { f: 'spread_ratio', w: '5.7%' },
              { f: 'atr_norm', w: '5.7%' },
              { f: 'rsi_slope', w: '5.3%' },
              { f: 'rsi', w: '4.9%' },
              { f: 'hour_cos', w: '4.5%' },
              { f: 'hour_sin', w: '2.9%' }
            ].map((item, idx) => (
              <span key={idx} style={{
                backgroundColor: 'var(--bg-base)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '2px 6px',
                fontSize: 10,
                color: 'var(--text-3)',
                fontFamily: 'JetBrains Mono, monospace'
              }}>
                <span style={{ color: 'var(--text-2)' }}>{item.f}</span>: {item.w}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Section 2: Multi-Timeframe Alignment ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        <div style={{ backgroundColor: 'var(--bg-card2)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>H4 bias</div>
          <div style={{
            fontSize: 11,
            fontWeight: 500,
            marginTop: 4,
            color: h4Bias.includes('BULL') ? 'var(--green)' : (h4Bias.includes('BEAR') ? 'var(--red)' : 'var(--text-2)')
          }}>
            {h4Bias.includes('BULL') ? 'Bullish' : (h4Bias.includes('BEAR') ? 'Bearish' : 'Range')}
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-card2)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>H1 trend</div>
          <div style={{
            fontSize: 11,
            fontWeight: 500,
            marginTop: 4,
            color: h1Trend.includes('BULL') ? 'var(--green)' : (h1Trend.includes('BEAR') ? 'var(--red)' : 'var(--text-2)')
          }}>
            {h1Trend.includes('BULL') ? 'Bullish' : (h1Trend.includes('BEAR') ? 'Bearish' : 'Neutral')}
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-card2)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>M1 entry Z</div>
          <div style={{ fontSize: 11, fontWeight: 500, marginTop: 4, color: 'var(--accent)' }} className="mono">
            {zM1}
          </div>
        </div>

        <div style={{ backgroundColor: 'var(--bg-card2)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-3)' }}>Regime</div>
          <div style={{ fontSize: 11, fontWeight: 500, marginTop: 4, color: 'var(--text-1)' }}>
            {regime}
          </div>
        </div>
      </div>

      {/* ── Section 3: Risk Factor & Lot Sizing ── */}
      <div style={{ backgroundColor: 'var(--bg-card2)', padding: 12, borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-2)' }}>Risk multiplier</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-1)' }} className="mono">
            {riskFactor.toFixed(1)}x
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 10 }}>
          {[
            { label: '0.5x Safe', val: 0.5 },
            { label: '1.0x Base', val: 1.0 },
            { label: '1.5x Dynamic', val: 1.5 },
            { label: '2.0x High', val: 2.0 }
          ].map(p => (
            <button
              key={p.val}
              type="button"
              onClick={() => updateRisk(p.val)}
              style={{
                backgroundColor: Math.abs(riskFactor - p.val) < 0.05 ? 'var(--text-1)' : 'var(--bg-base)',
                color: Math.abs(riskFactor - p.val) < 0.05 ? '#0b0d14' : 'var(--text-2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '4px 0',
                fontSize: 11,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'background-color 140ms var(--ease), color 140ms var(--ease)'
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        <input 
          type="range"
          min="0.1"
          max="3.0"
          step="0.1"
          value={riskFactor}
          onChange={(e) => updateRisk(e.target.value)}
          style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer', marginBottom: 8 }}
        />

        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: 'var(--bg-base)',
          padding: '8px 12px',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border)'
        }}>
          <div>
            <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Estimated lot volume: </span>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-1)' }} className="mono">
              {estimatedLot} lots
            </span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
            1.5x ATR trailing SL
          </div>
        </div>
      </div>

      {/* ── Section 4: Direct Action Buttons ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        <button
          type="button"
          disabled={actionLoading}
          onClick={() => handleFastTrade('BUY')}
          style={{
            backgroundColor: 'var(--green)',
            color: '#0b0d14',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontSize: 12,
            fontWeight: 500,
            cursor: actionLoading ? 'not-allowed' : 'pointer',
            boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.2)',
            transition: 'opacity 140ms var(--ease)'
          }}
        >
          Buy market
        </button>

        <button
          type="button"
          disabled={actionLoading}
          onClick={() => handleFastTrade('SELL')}
          style={{
            backgroundColor: 'var(--red)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontSize: 12,
            fontWeight: 500,
            cursor: actionLoading ? 'not-allowed' : 'pointer',
            boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.15)',
            transition: 'opacity 140ms var(--ease)'
          }}
        >
          Sell market
        </button>

        <button
          type="button"
          disabled={actionLoading}
          onClick={handleCloseAll}
          style={{
            backgroundColor: 'transparent',
            color: 'var(--red)',
            border: '1px solid rgba(229, 72, 77, 0.4)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontSize: 12,
            fontWeight: 500,
            cursor: actionLoading ? 'not-allowed' : 'pointer',
            transition: 'background-color 140ms var(--ease)'
          }}
        >
          Close all
        </button>
      </div>

      {/* ── Section 5: Positions & Trailing SL Monitor ── */}
      {isTrailing && (
        <div style={{
          backgroundColor: 'rgba(245, 158, 11, 0.05)',
          border: '1px solid rgba(245, 158, 11, 0.2)',
          padding: 10,
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: 8
        }}>
          <div style={{ color: 'var(--yellow)', fontSize: 11, fontWeight: 500 }}>
            Dynamic ATR trailing stop engaged on active positions
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ color: 'var(--text-3)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <th style={{ padding: '4px 6px' }}>Order</th>
                  <th style={{ padding: '4px 6px' }}>Direction</th>
                  <th style={{ padding: '4px 6px' }}>Volume</th>
                  <th style={{ padding: '4px 6px' }}>Entry</th>
                  <th style={{ padding: '4px 6px' }}>Floating P&L</th>
                  <th style={{ padding: '4px 6px', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {openPositions.map((pos) => {
                  const pnl = pos.profit !== undefined ? pos.profit : 0;
                  const isBuy = pos.type === 0 || pos.type === 'BUY';
                  return (
                    <tr key={pos.ticket} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '6px' }} className="mono">#{pos.ticket}</td>
                      <td style={{ padding: '6px' }}>
                        <span style={{
                          color: isBuy ? 'var(--green)' : 'var(--red)',
                          fontWeight: 500,
                          fontSize: 11
                        }}>
                          {isBuy ? 'Buy' : 'Sell'}
                        </span>
                      </td>
                      <td style={{ padding: '6px' }} className="mono">{pos.volume}</td>
                      <td style={{ padding: '6px' }} className="mono">${pos.price_open?.toFixed(2) || '—'}</td>
                      <td style={{ padding: '6px', color: pnl >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 500 }} className="mono">
                        {pnl >= 0 ? `+$${pnl.toFixed(2)}` : `-$${Math.abs(pnl).toFixed(2)}`}
                      </td>
                      <td style={{ padding: '6px', textAlign: 'right' }}>
                        <button
                          type="button"
                          onClick={() => handleCloseTicket(pos.ticket)}
                          style={{
                            background: 'transparent',
                            border: '1px solid var(--border)',
                            color: 'var(--text-2)',
                            borderRadius: 'var(--radius-sm)',
                            padding: '2px 6px',
                            fontSize: 10,
                            cursor: 'pointer'
                          }}
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
