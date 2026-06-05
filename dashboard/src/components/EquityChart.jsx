// src/components/EquityChart.jsx
// Real-time equity curve — reads from WebSocket data (instant updates)
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: 'var(--bg-card2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 14px', fontSize: 12,
    }}>
      <div style={{ color: 'var(--text-2)', marginBottom: 4 }}>
        {d.time ? new Date(d.time).toLocaleString() : label}
      </div>
      <div style={{ color: d.equity >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
        Equity: ${d.equity?.toFixed(2)}
      </div>
      <div style={{ color: 'var(--text-2)' }}>
        Trade PnL: {d.pnl >= 0 ? '+' : ''}${d.pnl?.toFixed(2)}
      </div>
    </div>
  );
}

export default function EquityChart({ equityData, loading = false }) {
  const points = equityData?.points ?? [];
  const isUp   = (equityData?.total_pnl ?? 0) >= 0;

  return (
    <div className="card">
      <div className="section-header" style={{ marginBottom: 16 }}>
        <div className="section-title">Equity Curve</div>
        <span className={isUp ? 'positive' : 'negative'} style={{ fontWeight: 700 }}>
          {isUp ? '+' : ''}${(equityData?.total_pnl ?? 0).toFixed(2)}
        </span>
      </div>

      {loading ? (
        <div className="spinner"><span className="spin">⟳</span></div>
      ) : points.length === 0 ? (
        <div className="spinner" style={{ height: 180, color: 'var(--text-3)' }}>
          No completed trades yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={isUp ? '#10b981' : '#ef4444'} stopOpacity={0.3} />
                <stop offset="95%" stopColor={isUp ? '#10b981' : '#ef4444'} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="time" hide />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--text-2)' }}
              tickLine={false} axisLine={false}
              tickFormatter={v => `$${v}`}
              width={60}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
            <Area
              type="monotone" dataKey="equity"
              stroke={isUp ? '#10b981' : '#ef4444'}
              strokeWidth={2} fill="url(#eq)"
              dot={false} activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
