// src/components/Analytics.jsx
// Real-time performance analytics — reads from WebSocket data (instant updates)

function AnalyticsSection({ title, data }) {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', marginBottom: 10 }}>
        {title}
      </div>
      {Object.entries(data).map(([key, v]) => (
        <div key={key} className="analytics-row">
          <span className="analytics-label">{key}</span>
          <div className="analytics-bar">
            <div className="analytics-fill" style={{ width: `${v.win_rate ?? 0}%` }} />
          </div>
          <span className="analytics-pct">{v.win_rate ?? 0}%</span>
          <span className="analytics-count">{v.wins}/{v.total}</span>
        </div>
      ))}
    </div>
  );
}

export default function Analytics({ analyticsData, loading = false }) {
  const s = analyticsData?.summary;
  const hasData = s && s.total > 0;

  return (
    <div className="card">
      <div className="section-title" style={{ marginBottom: 16 }}>Performance Analytics</div>

      {loading && <div className="spinner"><span className="spin">⟳</span></div>}

      {!loading && !hasData && (
        <div className="no-data-message" style={{ 
          height: 120, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          color: 'var(--text-3)', 
          fontSize: 14, 
          border: '1px dashed var(--border)', 
          borderRadius: 8, 
          marginTop: 10 
        }}>
          No trade data for this user
        </div>
      )}

      {hasData && (
        <>
          <div className="grid-4" style={{ marginBottom: 20 }}>
            {[
              ['Win Rate',      `${s.win_rate}%`],
              ['Profit Factor', s.profit_factor === 999 ? '∞' : s.profit_factor],
              ['Avg PnL',       `$${s.avg_pnl}`],
              ['Best Trade',    `$${s.best}`],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 2 }}>{l}</div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{v ?? '—'}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <AnalyticsSection title="By Session"    data={analyticsData?.by_session} />
            <AnalyticsSection title="By Score Range" data={analyticsData?.by_score} />
            <AnalyticsSection title="By Regime"     data={analyticsData?.by_regime} />
          </div>
        </>
      )}
    </div>
  );
}
