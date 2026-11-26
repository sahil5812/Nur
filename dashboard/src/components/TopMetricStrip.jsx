// src/components/TopMetricStrip.jsx — Institutional Top Metric Strip (Ivory & Brushed Gold)
import React from 'react';
import { formatCurrency } from '../utils/currency';

export default function TopMetricStrip({ stats, currency = 'INR' }) {
  const balance = stats?.balance ?? 4968.07;
  const equity = stats?.equity ?? 4968.07;
  const todayPnl = stats?.today_pnl ?? 0.0;
  const totalPnl = stats?.total_pnl ?? 31.99;
  const winRate = stats?.win_rate ?? 59.0;

  const isTodayPositive = todayPnl >= 0;
  const isTotalPositive = totalPnl >= 0;

  return (
    <div className="top-metric-strip">
      {/* ── 1. Portfolio Value Card ── */}
      <div className="top-metric-card portfolio-metric-card">
        <div className="top-metric-title">Portfolio Value</div>
        <div className="portfolio-values-row">
          <div className="portfolio-col">
            <div className="top-metric-val mono">{formatCurrency(balance, currency)}</div>
            <div className="top-metric-sub">Balance</div>
          </div>
          <div className="portfolio-col">
            <div className="top-metric-val mono">{formatCurrency(equity, currency)}</div>
            <div className="top-metric-sub">Equity</div>
          </div>
        </div>
      </div>

      {/* ── 2. Today's P&L Card ── */}
      <div className="top-metric-card">
        <div className="top-metric-title">Today's P&L</div>
        <div className={`top-metric-val mono ${isTodayPositive ? 'positive' : 'negative'}`}>
          {formatCurrency(todayPnl, currency, true)}
        </div>
        <div className="top-metric-sub" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>Today's P&L</span>
          <div className="pnl-mini-track">
            <div 
              className="pnl-mini-fill" 
              style={{ 
                width: `${Math.min(100, Math.max(15, Math.abs(todayPnl) * 2))}%`,
                backgroundColor: isTodayPositive ? 'var(--green)' : 'var(--red)'
              }} 
            />
          </div>
        </div>
      </div>

      {/* ── 3. Total Realized Card ── */}
      <div className="top-metric-card">
        <div className="top-metric-title">Total Realized</div>
        <div className={`top-metric-val mono highlight-realized ${isTotalPositive ? 'positive' : 'negative'}`}>
          {formatCurrency(totalPnl, currency, true)}
        </div>
        <div className="top-metric-sub">
          <span>Net Cumulative P&L</span>
        </div>
      </div>

      {/* ── 4. Win Rate Meter Card ── */}
      <div className="top-metric-card winrate-card">
        <div className="winrate-left">
          <div className="top-metric-title">Win Rate</div>
          <div className="top-metric-val mono">{winRate.toFixed(1)}%</div>
          <div className="top-metric-sub">
            <span>{stats?.wins ?? 6}W / {stats?.losses ?? 6}L</span>
          </div>
        </div>
        <div className="gauge-icon-container" title={`Win Rate: ${winRate.toFixed(1)}%`}>
          <svg width="44" height="28" viewBox="0 0 44 28" className="gauge-dial-svg">
            <path d="M 4 24 A 18 18 0 0 1 40 24" fill="none" stroke="#d5c39c" strokeWidth="4" strokeLinecap="round" />
            <path 
              d="M 4 24 A 18 18 0 0 1 40 24" 
              fill="none" 
              stroke="#2e7d32" 
              strokeWidth="4" 
              strokeDasharray="56.5" 
              strokeDashoffset={56.5 - (56.5 * (winRate / 100))} 
              strokeLinecap="round" 
            />
            <circle cx="22" cy="24" r="3.5" fill="#4a3b22" />
            {/* Needle pointer */}
            <line 
              x1="22" 
              y1="24" 
              x2={22 + 14 * Math.cos(Math.PI * (1 - winRate / 100))} 
              y2={24 - 14 * Math.sin(Math.PI * (1 - winRate / 100))} 
              stroke="#a67c38" 
              strokeWidth="2" 
              strokeLinecap="round" 
            />
          </svg>
        </div>
      </div>
    </div>
  );
}
