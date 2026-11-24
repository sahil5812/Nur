// src/components/TradeHistory.jsx — Precision Execution Log
import React from 'react';
import { formatCurrency } from '../utils/currency';

export default function TradeHistory({ trades = [], total = 0, loading = false, currency = 'INR' }) {
  return (
    <div className="card">
      <div className="section-header">
        <div className="section-title">Recent trades</div>
        <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}>
          {total} total records
        </span>
      </div>

      {loading ? (
        <div className="spinner"><span className="spin">⟳</span></div>
      ) : trades.length === 0 ? (
        <div className="spinner" style={{ height: 120, color: 'var(--text-3)' }}>
          No completed trades recorded yet
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Execution time</th>
                <th>Direction</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>Lot</th>
                <th>Score</th>
                <th>Realized P&L</th>
                <th>Exit reason</th>
                <th>Mode</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => {
                const pnl = t.pnl ?? 0;
                const isBuy = t.direction === 'BUY' || t.direction === 0;
                return (
                  <tr key={t.id ?? i}>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      {t.exit_time ? new Date(t.exit_time).toLocaleTimeString() : '—'}
                    </td>
                    <td>
                      <span style={{
                        fontWeight: 500,
                        fontSize: 11,
                        color: isBuy ? 'var(--green)' : 'var(--red)',
                      }}>
                        {isBuy ? 'Buy' : 'Sell'}
                      </span>
                    </td>
                    <td className="mono">${t.entry_price?.toFixed(2) ?? '—'}</td>
                    <td className="mono">${t.exit_price?.toFixed(2) ?? '—'}</td>
                    <td className="mono">{t.lot ?? '—'}</td>
                    <td>
                      <div className="score-bar-wrap">
                        <div className="score-bar" style={{ width: 44 }}>
                          <div className="score-bar-fill" style={{ width: `${Math.min(100, t.score ?? 0)}%` }} />
                        </div>
                        <span className="score-val">{t.score ?? '—'}</span>
                      </div>
                    </td>
                    <td className={`mono ${pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : ''}`}
                        style={{ fontWeight: 500 }}>
                      {formatCurrency(pnl, currency, true)}
                    </td>
                    <td style={{ fontSize: 11, color: 'var(--text-3)' }}>{t.exit_reason ?? '—'}</td>
                    <td>
                      <span style={{
                        fontSize: 10,
                        fontWeight: 500,
                        padding: '2px 6px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--bg-card2)',
                        border: '1px solid var(--border)',
                        color: t.is_paper ? 'var(--text-2)' : 'var(--green)',
                      }}>
                        {t.is_paper ? 'Paper' : 'Live'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
