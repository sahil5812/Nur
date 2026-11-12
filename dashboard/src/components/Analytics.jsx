// src/components/Analytics.jsx — Quantitative Performance Analytics
import React from 'react';

function AnalyticsSection({ title, data }) {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-3)', marginBottom: 8 }}>
        {title}
      </div>
      {Object.entries(data).map(([key, v]) => (
        <div key={key} className="analytics-row">
          <span className="analytics-label">{key}</span>
          <div className="analytics-bar">
            <div className="analytics-fill" style={{ width: `${Math.min(100, v.win_rate ?? 0)}%` }} />
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
      <div className="section-title" style={{ marginBottom: 16 }}>Performance analytics</div>

      {loading && <div className="spinner"><span className="spin">⟳</span></div>}

      {!loading && !hasData && (
        <div style={{ 
          height: 120, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          color: 'var(--text-3)', 
          fontSize: 12, 
          border: '1px dashed var(--border)', 
          borderRadius: 'var(--radius-md)', 
          marginTop: 8 
        }}>
          No closed trade analytics available yet
        </div>
      )}

      {hasData && (
        <>
          <div className="grid-4" style={{ marginBottom: 20 }}>
            {[
              ['Win rate',       `${s.win_rate}%`],
              ['Profit factor',  s.profit_factor === 999 ? '∞' : s.profit_factor],
              ['Average trade',  `$${s.avg_pnl}`],
              ['Best trade',     `$${s.best}`],
            ].map(([label, val]) => (
              <div key={label}>
                <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 16, fontWeight: 500 }} className="mono">{val ?? '—'}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <AnalyticsSection title="By session"     data={analyticsData?.by_session} />
            <AnalyticsSection title="By score range" data={analyticsData?.by_score} />
            <AnalyticsSection title="By regime"      data={analyticsData?.by_regime} />
          </div>
        </>
      )}
    </div>
  );
}
