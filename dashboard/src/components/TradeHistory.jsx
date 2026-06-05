// src/components/TradeHistory.jsx
// Real-time trade history — reads from WebSocket data (instant updates)

export default function TradeHistory({ trades = [], total = 0, loading = false }) {
  return (
    <div className="card">
      <div className="section-header" style={{ marginBottom: 14 }}>
        <div className="section-title">Recent Trades</div>
        <span style={{ fontSize: 12, color: 'var(--text-2)' }}>
          {total} total
        </span>
      </div>

      {loading ? (
        <div className="spinner"><span className="spin">⟳</span></div>
      ) : trades.length === 0 ? (
        <div className="spinner" style={{ height: 120, color: 'var(--text-3)' }}>
          No completed trades yet
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Dir</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>Lot</th>
                <th>Score</th>
                <th>PnL</th>
                <th>Reason</th>
                <th>Mode</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => {
                const pnl = t.pnl ?? 0;
                return (
                  <tr key={t.id ?? i}>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>
                      {t.exit_time ? new Date(t.exit_time).toLocaleString() : '—'}
                    </td>
                    <td>
                      <span style={{
                        fontWeight: 600, fontSize: 12,
                        color: t.direction === 'BUY' ? 'var(--green)' : 'var(--red)',
                      }}>{t.direction}</span>
                    </td>
                    <td className="mono">${t.entry_price?.toFixed(2) ?? '—'}</td>
                    <td className="mono">${t.exit_price?.toFixed(2) ?? '—'}</td>
                    <td>{t.lot ?? '—'}</td>
                    <td>
                      <div className="score-bar-wrap">
                        <div className="score-bar" style={{ width: 40 }}>
                          <div className="score-bar-fill" style={{ width: `${t.score ?? 0}%` }} />
                        </div>
                        <span className="score-val">{t.score ?? '—'}</span>
                      </div>
                    </td>
                    <td className={`mono ${pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : ''}`}
                        style={{ fontWeight: 600 }}>
                      {pnl > 0 ? '+' : ''}${pnl.toFixed(2)}
                    </td>
                    <td style={{ fontSize: 11, color: 'var(--text-2)' }}>{t.exit_reason ?? '—'}</td>
                    <td>
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: '2px 6px',
                        borderRadius: 4,
                        background: t.is_paper ? 'rgba(99,102,241,0.15)' : 'rgba(16,185,129,0.15)',
                        color: t.is_paper ? '#818cf8' : 'var(--green)',
                      }}>
                        {t.is_paper ? 'PAPER' : 'LIVE'}
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
