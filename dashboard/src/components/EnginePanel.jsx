// src/components/EnginePanel.jsx
// Shows live engine state: price, EMA, trend, regime, float PnL
export default function EnginePanel({ engine, stats }) {
  if (!engine) return null;

  const regime  = engine.trend || 'TRENDING';
  const regimeClass = `regime-badge regime-${regime.replace(/\s/g, '_').toUpperCase()}`;
  const floatPnl = 0; // float PnL comes from positions (future)

  return (
    <div className="card">
      <div className="card-title">Engine Status</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px' }}>
        <Row label="State"   value={engine.state  || '—'} />
        <Row label="Price"   value={engine.last_close ? `$${engine.last_close}` : '—'} />
        <Row label="EMA 200" value={engine.ema200  ? `$${engine.ema200}` : '—'} />
        <Row label="H1 Trend" value={engine.trend  || '—'} />
        <div style={{ gridColumn: '1/-1', display: 'flex', alignItems: 'center', gap: 8, paddingTop: 4 }}>
          <span style={{ fontSize: 12, color: 'var(--text-2)' }}>Regime</span>
          <span className={regimeClass}>{regime}</span>
        </div>
        {stats?.trading_locked && (
          <div style={{ gridColumn: '1/-1' }}>
            <span style={{
              background: 'rgba(239,68,68,0.1)', color: 'var(--red)',
              border: '1px solid var(--red)', borderRadius: 6,
              padding: '4px 10px', fontSize: 12, fontWeight: 600,
            }}>🔒 TRADING LOCKED</span>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600 }} className="mono">{value}</div>
    </div>
  );
}
