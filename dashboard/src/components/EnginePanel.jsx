// src/components/EnginePanel.jsx — Quiet Instrument Telemetry
import React from 'react';

export default function EnginePanel({ engine, stats }) {
  if (!engine) return null;

  const regime  = engine.trend || 'TRENDING';
  const regimeClass = `regime-badge regime-${regime.replace(/\s/g, '_').toUpperCase()}`;

  return (
    <div className="card">
      <div className="section-header">
        <div className="section-title">Engine status</div>
        {stats?.trading_locked && (
          <span style={{
            backgroundColor: 'rgba(229, 72, 77, 0.1)',
            color: 'var(--red)',
            border: '1px solid rgba(229, 72, 77, 0.25)',
            borderRadius: 'var(--radius-sm)',
            padding: '2px 8px',
            fontSize: 11,
            fontWeight: 500,
          }}>
            Trading locked
          </span>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 20px' }}>
        <MetricRow label="Execution state" value={engine.state || 'Waiting'} />
        <MetricRow label="Spot price" value={engine.last_close ? `$${Number(engine.last_close).toFixed(2)}` : '—'} />
        <MetricRow label="200 EMA" value={engine.ema200 ? `$${Number(engine.ema200).toFixed(2)}` : '—'} />
        <MetricRow label="H1 trend" value={engine.trend || 'None'} />
        
        <div style={{ gridColumn: '1/-1', display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 4, borderTop: '1px solid var(--border-subtle)' }}>
          <span style={{ fontSize: 12, color: 'var(--text-3)' }}>Regime classification</span>
          <span className={regimeClass}>{regime}</span>
        </div>
      </div>
    </div>
  );
}

function MetricRow({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-1)' }} className="mono">{value}</div>
    </div>
  );
}
