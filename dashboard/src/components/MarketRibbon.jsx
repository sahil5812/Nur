// src/components/MarketRibbon.jsx — High-Density Institutional Ticker Ribbon
import React from 'react';

export default function MarketRibbon({ stats, engine, connected }) {
  const balance = stats?.balance ?? 5000.0;
  const equity = stats?.equity ?? balance;
  const todayPnl = stats?.today_pnl ?? 0.0;
  const totalPnl = stats?.total_pnl ?? 0.0;
  const winRate = stats?.win_rate ?? 0.0;
  const totalTrades = stats?.total_trades ?? 0;
  const wins = stats?.wins ?? 0;
  const losses = stats?.losses ?? 0;
  const openPos = stats?.open_positions ?? 0;

  const isUpToday = todayPnl > 0;
  const isDownToday = todayPnl < 0;

  return (
    <div className="market-ribbon">
      <div className="ribbon-inner">
        {/* Metric 1: Account Balance */}
        <div className="ribbon-item">
          <span className="ribbon-label">Balance</span>
          <span className="ribbon-val mono">${Number(balance).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>

        <div className="ribbon-divider" />

        {/* Metric 2: Account Equity */}
        <div className="ribbon-item">
          <span className="ribbon-label">Equity</span>
          <span className="ribbon-val mono">${Number(equity).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>

        <div className="ribbon-divider" />

        {/* Metric 3: Today P&L */}
        <div className="ribbon-item">
          <span className="ribbon-label">Today P&L</span>
          <span className={`ribbon-val mono ${isUpToday ? 'positive' : isDownToday ? 'negative' : 'neutral'}`}>
            {isUpToday ? '+' : ''}${todayPnl.toFixed(2)}
          </span>
        </div>

        <div className="ribbon-divider" />

        {/* Metric 4: Total Realized P&L */}
        <div className="ribbon-item">
          <span className="ribbon-label">Total Realized</span>
          <span className={`ribbon-val mono ${totalPnl > 0 ? 'positive' : totalPnl < 0 ? 'negative' : 'neutral'}`}>
            {totalPnl > 0 ? '+' : ''}${totalPnl.toFixed(2)}
          </span>
        </div>

        <div className="ribbon-divider" />

        {/* Metric 5: Win Rate */}
        <div className="ribbon-item">
          <span className="ribbon-label">Win Rate</span>
          <span className="ribbon-val mono">
            {winRate.toFixed(1)}% <span className="ribbon-sub">({wins}W / {losses}L)</span>
          </span>
        </div>

        <div className="ribbon-divider" />

        {/* Metric 6: Exposure / Open Positions */}
        <div className="ribbon-item">
          <span className="ribbon-label">Active Exposure</span>
          <span className="ribbon-val mono">
            {openPos} open <span className="ribbon-sub">({totalTrades} closed)</span>
          </span>
        </div>

        <div className="ribbon-divider" />

        {/* Metric 7: Daily Loss Guard */}
        <div className="ribbon-item">
          <span className="ribbon-label">Daily Guard</span>
          <span className="ribbon-val mono" style={{ color: 'var(--text-2)' }}>
            $50.00 max <span className="ribbon-sub">(Safe)</span>
          </span>
        </div>
      </div>
    </div>
  );
}
