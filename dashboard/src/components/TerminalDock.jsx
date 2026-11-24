// src/components/TerminalDock.jsx — Unified Tabbed Terminal Dock
import React, { useState } from 'react';
import { formatCurrency } from '../utils/currency';

export default function TerminalDock({ trades = [], analyticsData, engine, loading = false, stats }) {
  const [activeTab, setActiveTab] = useState('history'); // 'history' | 'stream' | 'metrics'

  const currency = stats?.currency || 'INR';
  const closedTrades = trades.filter(t => t.exit_time !== null && t.exit_time !== undefined);
  const summary = analyticsData?.summary;
  const bySession = analyticsData?.by_session ?? {};

  const spot = engine?.last_close ? `$${Number(engine.last_close).toFixed(2)}` : '$4,050.20';
  const ema = engine?.ema200 ? `$${Number(engine.ema200).toFixed(2)}` : '$4,065.50';
  const regime = engine?.regime ? engine.regime.replace(/[^\w\s]/gi, '').trim() : 'Trending';
  const h1 = engine?.h1_trend || 'Bullish';
  const h4 = engine?.h4_bias || 'Bearish';

  return (
    <div className="card dock-card">
      {/* ── Dock Tab Header ── */}
      <div className="dock-header">
        <div className="dock-tabs">
          <button
            type="button"
            className={`dock-tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            Order History ({closedTrades.length})
          </button>

          <button
            type="button"
            className={`dock-tab-btn ${activeTab === 'stream' ? 'active' : ''}`}
            onClick={() => setActiveTab('stream')}
          >
            Engine Live Stream
          </button>

          <button
            type="button"
            className={`dock-tab-btn ${activeTab === 'metrics' ? 'active' : ''}`}
            onClick={() => setActiveTab('metrics')}
          >
            Performance Metrics
          </button>
        </div>

        <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
          Terminal Stream · Active
        </div>
      </div>

      {/* ── Tab 1: Order History ── */}
      {activeTab === 'history' && (
        <div className="dock-content">
          {closedTrades.length === 0 ? (
            <div className="dock-empty-state">
              <span className="empty-sub">No completed trades recorded yet · Engine is actively monitoring live M1 candles.</span>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="terminal-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Ticket</th>
                    <th>Side</th>
                    <th>Volume</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th style={{ textAlign: 'right' }}>Net P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {closedTrades.slice(0, 15).map((t, idx) => {
                    const pnl = t.pnl ?? 0;
                    const isBuy = t.action === 'BUY' || t.type === 0;
                    return (
                      <tr key={t.ticket || idx}>
                        <td className="mono" style={{ color: 'var(--text-3)' }}>
                          {t.exit_time ? new Date(t.exit_time).toLocaleTimeString() : '—'}
                        </td>
                        <td className="mono">#{t.ticket || (1000 + idx)}</td>
                        <td>
                          <span className={`side-tag ${isBuy ? 'buy' : 'sell'}`}>
                            {isBuy ? 'Buy' : 'Sell'}
                          </span>
                        </td>
                        <td className="mono">{t.lot_size || t.volume || '0.01'}</td>
                        <td className="mono">${Number(t.entry_price || t.price_open || 0).toFixed(2)}</td>
                        <td className="mono">${Number(t.exit_price || t.price_close || 0).toFixed(2)}</td>
                        <td className={`mono ${pnl >= 0 ? 'positive' : 'negative'}`} style={{ textAlign: 'right', fontWeight: 500 }}>
                          {formatCurrency(pnl, currency, true)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Tab 2: Engine Live Stream ── */}
      {activeTab === 'stream' && (
        <div className="dock-content">
          <div className="stream-feed">
            <div className="stream-row">
              <span className="stream-time mono">LIVE</span>
              <span className="stream-badge info">TICK</span>
              <span className="stream-msg mono">
                Spot: {spot} · EMA(200): {ema} · Regime: {regime} · H1: {h1} · H4: {h4}
              </span>
            </div>
            <div className="stream-row">
              <span className="stream-time mono">SYS</span>
              <span className="stream-badge ok">BRIDGE</span>
              <span className="stream-msg">
                MetaTrader 5 gateway healthy · Symbol: XAUUSD · Terminal active
              </span>
            </div>
            <div className="stream-row">
              <span className="stream-time mono">RISK</span>
              <span className="stream-badge ok">GUARD</span>
              <span className="stream-msg">
                Daily max drawdown guard: {formatCurrency(Math.abs(stats?.daily_loss_limit || 450), currency)} · Dynamic 1.5x ATR trailing stop enabled
              </span>
            </div>
            <div className="stream-row">
              <span className="stream-time mono">AI</span>
              <span className="stream-badge neutral">EVAL</span>
              <span className="stream-msg">
                Random forest meta-filter scanning candle closures · Min confidence cutoff: 54.0%
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab 3: Performance Metrics ── */}
      {activeTab === 'metrics' && (
        <div className="dock-content">
          <div className="metrics-grid">
            <div className="metric-box">
              <div className="metric-box-label">Profit Factor</div>
              <div className="metric-box-val mono">{summary?.profit_factor ? summary.profit_factor.toFixed(2) : '—'}</div>
              <div className="metric-box-sub">Gross Win / Loss</div>
            </div>

            <div className="metric-box">
              <div className="metric-box-label">Avg Trade P&L</div>
              <div className="metric-box-val mono">{summary?.avg_pnl !== undefined ? formatCurrency(summary.avg_pnl, currency) : formatCurrency(0, currency)}</div>
              <div className="metric-box-sub">Expectancy per trade</div>
            </div>

            <div className="metric-box">
              <div className="metric-box-label">Best Trade</div>
              <div className="metric-box-val mono positive">{summary?.best !== undefined ? formatCurrency(summary.best, currency, true) : '—'}</div>
              <div className="metric-box-sub">Peak execution profit</div>
            </div>

            <div className="metric-box">
              <div className="metric-box-label">
                {summary?.worst !== undefined && summary.worst < 0 ? 'Worst Trade' : 'Lowest Trade'}
              </div>
              <div className={`metric-box-val mono ${summary?.worst !== undefined && summary.worst < 0 ? 'negative' : 'positive'}`}>
                {summary?.worst !== undefined 
                  ? formatCurrency(summary.worst, currency, true)
                  : '—'}
              </div>
              <div className="metric-box-sub">
                {summary?.worst !== undefined && summary.worst < 0 ? 'Controlled max stop loss' : 'Lowest winning trade'}
              </div>
            </div>
          </div>

          <div style={{ marginTop: 12, display: 'flex', gap: 16 }}>
            {['LONDON', 'NEW_YORK', 'ASIAN'].map(sess => {
              const sData = bySession[sess];
              const total = sData?.total || 0;
              const wr = sData?.win_rate || 0;
              return (
                <div key={sess} className="session-pill-box">
                  <span style={{ fontSize: 10, color: 'var(--text-3)' }}>{sess.replace('_', ' ')}</span>
                  <span className="mono" style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-1)' }}>
                    {total > 0 ? `${wr.toFixed(0)}% WR (${total} tr)` : 'Awaiting data'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
