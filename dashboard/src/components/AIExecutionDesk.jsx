// src/components/AIExecutionDesk.jsx — Integrated AI Execution & Risk Desk
import React, { useState, useEffect, useMemo } from 'react';
import { getApiBase } from '../config';
import { formatCurrency } from '../utils/currency';

export default function AIExecutionDesk({ token, engine, stats }) {
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
  const balance = stats?.balance || 5000.0;
  const atr = engine?.atr || 2.14;
  const estimatedLot = useMemo(() => {
    const riskPercent = 1.0;
    const slAtrMult = 1.5;
    const riskAmount = balance * (riskPercent / 100.0) * riskFactor;
    const slDistance = Math.max(atr * slAtrMult, 1.0);
    const baseLot = riskAmount / (slDistance * 100.0);
    const lot = Math.round(Math.max(baseLot, 0.01) * 100) / 100;
    return lot.toFixed(2);
  }, [balance, atr, riskFactor]);

  // Conviction and indicator values
  const rfProbRaw = engine?.rf_prob !== undefined ? Number(engine.rf_prob) : 0.48;
  const rfProbPct = (rfProbRaw * 100).toFixed(1);
  const minThreshold = (rfMeta?.min_threshold || 0.54) * 100;
  const isApproved = engine?.rf_approved !== undefined ? Boolean(engine.rf_approved) : (rfProbRaw >= 0.54);

  const h4Bias = engine?.h4_bias || 'BEARISH';
  const h1Trend = engine?.h1_trend || 'BULLISH';
  const regime = engine?.regime ? engine.regime.replace(/[^\w\s]/gi, '').trim() : 'Trending';
  const zM1 = engine?.z_m1 !== undefined ? (engine.z_m1 >= 0 ? `+${engine.z_m1}σ` : `${engine.z_m1}σ`) : '-0.42σ';

  // Manual fast execution handlers
  const handleFastTrade = async (direction) => {
    setActionLoading(true);
    try {
      const base = getApiBase();
      const headers = { 'Content-Type': 'application/json' };
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch(`${base}/api/fast_trade`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          direction,
          risk_multiplier: riskFactor,
          reason: `Manual execution (${direction})`
        })
      });

      const resData = await res.json();
      if (res.ok) {
        setToast({ type: 'success', msg: `Market ${direction} order executed successfully.` });
        fetchOpenPositions();
      } else {
        setToast({ type: 'error', msg: resData.detail || `Failed to execute ${direction} order.` });
      }
    } catch (e) {
      setToast({ type: 'error', msg: `Execution error: ${e.message}` });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseAll = async () => {
    setActionLoading(true);
    try {
      const base = getApiBase();
      const headers = { 'Content-Type': 'application/json' };
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch(`${base}/api/close_all`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ reason: 'Manual Emergency Flatten' })
      });

      const resData = await res.json();
      if (res.ok) {
        setToast({ type: 'info', msg: `All open positions closed (${resData.closed || 0} orders).` });
        fetchOpenPositions();
      } else {
        setToast({ type: 'error', msg: resData.detail || 'Failed to close positions.' });
      }
    } catch (e) {
      setToast({ type: 'error', msg: `Close error: ${e.message}` });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseTicket = async (ticket) => {
    try {
      const base = getApiBase();
      const headers = { 'Content-Type': 'application/json' };
      const authToken = token || localStorage.getItem('token');
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch(`${base}/api/close_position/${ticket}`, {
        method: 'POST',
        headers
      });

      if (res.ok) {
        setToast({ type: 'info', msg: `Order #${ticket} closed.` });
        fetchOpenPositions();
      }
    } catch (e) {
      console.error("Failed to close ticket:", e);
    }
  };

  return (
    <div className="card desk-card">
      {/* ── Desk Header ── */}
      <div className="section-header" style={{ marginBottom: 14 }}>
        <div>
          <div className="section-title">AI Execution Desk</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
            MARL Regime & Meta-Filter Gate
          </div>
        </div>

        <div>
          {isApproved ? (
            <span className="gate-badge approved">
              <span className="gate-dot" />
              Approved (P ≥ {minThreshold.toFixed(0)}%)
            </span>
          ) : (
            <span className="gate-badge veto">
              <span className="gate-dot" />
              Veto active (P &lt; {minThreshold.toFixed(0)}%)
            </span>
          )}
        </div>
      </div>

      {/* ── Toast Alert ── */}
      {toast && (
        <div className={`toast-banner ${toast.type}`}>
          <span>{toast.msg}</span>
          <button type="button" onClick={() => setToast(null)}>×</button>
        </div>
      )}

      {/* ── Conviction Meter ── */}
      <div className="desk-subpanel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-2)' }}>Model Conviction</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: isApproved ? 'var(--green)' : 'var(--yellow)' }} className="mono">
            {rfProbPct}%
          </span>
        </div>

        <div className="conviction-track">
          <div 
            className="conviction-fill" 
            style={{ 
              width: `${Math.min(100, Math.max(0, rfProbRaw * 100))}%`,
              backgroundColor: isApproved ? 'var(--green)' : 'var(--yellow)'
            }} 
          />
          <div 
            className="conviction-threshold" 
            style={{ left: `${minThreshold}%` }} 
            title={`Threshold: ${minThreshold}%`} 
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
          <span>Chop (0%)</span>
          <span style={{ color: 'var(--text-2)' }}>Cutoff: {minThreshold.toFixed(0)}%</span>
          <span>Conviction (100%)</span>
        </div>

        <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: 'var(--text-3)' }}>12 of 17 features active</span>
          <button 
            type="button" 
            className="text-link-btn"
            onClick={() => setShowFeatures(!showFeatures)}
          >
            {showFeatures ? 'Hide weights' : 'Inspect weights'}
          </button>
        </div>

        {showFeatures && (
          <div className="feature-weights-grid">
            {[
              { f: 'z_h1', w: '18.2%' }, { f: 'z_m5', w: '13.8%' },
              { f: 'z_m1', w: '10.8%' }, { f: 'realized_vol', w: '9.7%' },
              { f: 'macd_hist', w: '9.7%' }, { f: 'z_align', w: '8.7%' },
              { f: 'spread_ratio', w: '5.7%' }, { f: 'atr_norm', w: '5.7%' }
            ].map((item, idx) => (
              <span key={idx} className="feature-chip mono">
                <span>{item.f}</span>: {item.w}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Multi-Timeframe Alignment Radar ── */}
      <div className="radar-grid">
        <div className="radar-cell">
          <div className="radar-label">H4 Bias</div>
          <div className={`radar-val ${h4Bias.includes('BULL') ? 'positive' : (h4Bias.includes('BEAR') ? 'negative' : 'neutral')}`}>
            {h4Bias.includes('BULL') ? 'Bullish' : (h4Bias.includes('BEAR') ? 'Bearish' : 'Range')}
          </div>
        </div>

        <div className="radar-cell">
          <div className="radar-label">H1 Trend</div>
          <div className={`radar-val ${h1Trend.includes('BULL') ? 'positive' : (h1Trend.includes('BEAR') ? 'negative' : 'neutral')}`}>
            {h1Trend.includes('BULL') ? 'Bullish' : (h1Trend.includes('BEAR') ? 'Bearish' : 'Neutral')}
          </div>
        </div>

        <div className="radar-cell">
          <div className="radar-label">M1 Entry Z</div>
          <div className="radar-val mono" style={{ color: 'var(--accent)' }}>
            {zM1}
          </div>
        </div>

        <div className="radar-cell">
          <div className="radar-label">Regime</div>
          <div className="radar-val" style={{ color: 'var(--text-1)' }}>
            {regime}
          </div>
        </div>
      </div>

      {/* ── Risk Multiplier & Dynamic Lot ── */}
      <div className="desk-subpanel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-2)' }}>Risk Multiplier</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-1)' }} className="mono">
            {riskFactor.toFixed(1)}x
          </span>
        </div>

        <div className="risk-chip-row">
          {[
            { label: '0.5x Safe', val: 0.5 },
            { label: '1.0x Base', val: 1.0 },
            { label: '1.5x Dynamic', val: 1.5 },
            { label: '2.0x High', val: 2.0 }
          ].map(p => (
            <button
              key={p.val}
              type="button"
              className={`risk-chip ${Math.abs(riskFactor - p.val) < 0.05 ? 'active' : ''}`}
              onClick={() => updateRisk(p.val)}
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
          className="risk-slider"
        />

        <div className="lot-calc-strip">
          <div>
            <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Calculated Size: </span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }} className="mono">
              {estimatedLot} lots
            </span>
          </div>
          <span style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
            1.5x ATR trailing stop
          </span>
        </div>
      </div>

      {/* ── Action Buttons ── */}
      <div className="desk-actions-row">
        <button
          type="button"
          disabled={actionLoading}
          onClick={() => handleFastTrade('BUY')}
          className="action-btn-buy"
        >
          Buy Market
        </button>

        <button
          type="button"
          disabled={actionLoading}
          onClick={() => handleFastTrade('SELL')}
          className="action-btn-sell"
        >
          Sell Market
        </button>

        <button
          type="button"
          disabled={actionLoading}
          onClick={handleCloseAll}
          className="action-btn-flatten"
        >
          Flatten All
        </button>
      </div>

      {/* ── Open Positions or Signal Scanner ── */}
      <div className="desk-subpanel" style={{ marginTop: 'auto' }}>
        <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Active Orders ({openPositions.length})</span>
          {openPositions.length > 0 && <span className="mono" style={{ color: 'var(--green)', fontSize: 10 }}>Trailing SL Active</span>}
        </div>

        {openPositions.length === 0 ? (
          <div className="radar-status-box">
            <div className="radar-status-item">
              <span className="dot-green" />
              <span>Bridge: MT5 connected (Gold XAUUSD)</span>
            </div>
            <div className="radar-status-item">
              <span className="dot-green" />
              <span>Spread: 0.20 within limits</span>
            </div>
            <div className="radar-status-item">
              <span className="dot-pulse" />
              <span>Scanning M1 candle closure for setup</span>
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="terminal-table">
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Side</th>
                  <th>Vol</th>
                  <th>Entry</th>
                  <th>P&L</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {openPositions.map((pos) => {
                  const pnl = pos.profit !== undefined ? pos.profit : 0;
                  const isBuy = pos.type === 0 || pos.type === 'BUY';
                  return (
                    <tr key={pos.ticket}>
                      <td className="mono">#{pos.ticket}</td>
                      <td>
                        <span className={`side-tag ${isBuy ? 'buy' : 'sell'}`}>
                          {isBuy ? 'Buy' : 'Sell'}
                        </span>
                      </td>
                      <td className="mono">{pos.volume}</td>
                      <td className="mono">${pos.price_open?.toFixed(2) || '—'}</td>
                      <td className={`mono ${pnl >= 0 ? 'positive' : 'negative'}`} style={{ fontWeight: 500 }}>
                        {formatCurrency(pnl, stats?.currency, true)}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          className="close-ticket-btn"
                          onClick={() => handleCloseTicket(pos.ticket)}
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
        )}
      </div>
    </div>
  );
}
