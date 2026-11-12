// src/components/StatCards.jsx — Precision Instrument KPI Cards
import React from 'react';

function StatCard({ label, value, sub, colorClass = 'neutral' }) {
  return (
    <div className="card">
      <div className="card-title">{label}</div>
      <div className={`stat-value ${colorClass}`}>{value ?? '—'}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export default function StatCards({ stats }) {
  if (!stats) return null;

  const pnl      = stats.today_pnl ?? 0;
  const total    = stats.total_pnl ?? 0;
  const winRate  = stats.win_rate  ?? 0;
  const streak   = stats.win_streak > 0
    ? `+${stats.win_streak} wins`
    : stats.loss_streak > 0
    ? `-${stats.loss_streak} losses`
    : 'None';

  return (
    <div className="grid-4">
      <StatCard
        label="Today P&L"
        value={`$${pnl.toFixed(2)}`}
        sub={`${stats.today_trades ?? 0} trades today`}
        colorClass={pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral'}
      />
      <StatCard
        label="Total P&L"
        value={`$${total.toFixed(2)}`}
        sub={`${stats.total_trades ?? 0} total trades`}
        colorClass={total > 0 ? 'positive' : total < 0 ? 'negative' : 'neutral'}
      />
      <StatCard
        label="Win rate"
        value={`${winRate.toFixed(1)}%`}
        sub={`${stats.wins ?? 0}W · ${stats.losses ?? 0}L`}
        colorClass={winRate >= 50 ? 'positive' : 'negative'}
      />
      <StatCard
        label="Current streak"
        value={streak}
        sub={`Max: +${stats.max_win_streak ?? 0}W · -${stats.max_loss_streak ?? 0}L`}
      />
    </div>
  );
}
