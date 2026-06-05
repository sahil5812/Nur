// src/components/StatCards.jsx
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
    ? `🔥 W${stats.win_streak}`
    : stats.loss_streak > 0
    ? `❄️ L${stats.loss_streak}`
    : '—';

  return (
    <div className="grid-4">
      <StatCard
        label="Today PnL"
        value={`$${pnl.toFixed(2)}`}
        sub={`${stats.today_trades ?? 0} trades today`}
        colorClass={pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral'}
      />
      <StatCard
        label="Total PnL"
        value={`$${total.toFixed(2)}`}
        sub={`${stats.total_trades ?? 0} all-time trades`}
        colorClass={total > 0 ? 'positive' : total < 0 ? 'negative' : 'neutral'}
      />
      <StatCard
        label="Win Rate"
        value={`${winRate}%`}
        sub={`${stats.wins ?? 0}W / ${stats.losses ?? 0}L`}
        colorClass={winRate >= 50 ? 'positive' : 'negative'}
      />
      <StatCard
        label="Streak"
        value={streak}
        sub={`Best W: ${stats.max_win_streak ?? 0}  |  Max L: ${stats.max_loss_streak ?? 0}`}
      />
    </div>
  );
}
