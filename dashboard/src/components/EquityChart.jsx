// src/components/EquityChart.jsx — High-Craft Capital Trajectory Canvas
import React from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      backgroundColor: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-sm)',
      padding: '8px 12px',
      fontSize: 11,
      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)'
    }}>
      <div style={{ color: 'var(--text-3)', marginBottom: 4 }}>
        {d.time ? new Date(d.time).toLocaleTimeString() : label}
      </div>
      <div style={{ color: d.equity >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 500 }} className="mono">
        Equity: ${d.equity?.toFixed(2)}
      </div>
      <div style={{ color: 'var(--text-2)' }} className="mono">
        Trade: {d.pnl >= 0 ? '+' : ''}${d.pnl?.toFixed(2)}
      </div>
    </div>
  );
}

export default function EquityChart({ equityData, loading = false }) {
  const points = equityData?.points ?? [];
  const isUp   = (equityData?.total_pnl ?? 0) >= 0;
  const strokeColor = isUp ? 'var(--green)' : 'var(--red)';

  return (
    <div className="card">
      <div className="section-header">
        <div className="section-title">Equity curve</div>
        <span className={`mono ${isUp ? 'positive' : 'negative'}`} style={{ fontWeight: 500, fontSize: 13 }}>
          {isUp ? '+' : ''}${(equityData?.total_pnl ?? 0).toFixed(2)}
        </span>
      </div>

      {loading ? (
        <div className="spinner"><span className="spin">⟳</span></div>
      ) : points.length === 0 ? (
        <div className="spinner" style={{ height: 220, color: 'var(--text-3)' }}>
          No completed trades recorded yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={points} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={strokeColor} stopOpacity={0.15} />
                <stop offset="100%" stopColor={strokeColor} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(238, 240, 245, 0.04)" vertical={false} />
            <XAxis dataKey="time" hide />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={v => `$${v}`}
              width={64}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="rgba(238, 240, 245, 0.1)" strokeDasharray="3 3" />
            <Area
              type="monotone"
              dataKey="equity"
              stroke={strokeColor}
              strokeWidth={1.5}
              fill="url(#eqFill)"
              dot={false}
              activeDot={{ r: 3, fill: strokeColor, stroke: 'var(--bg-card)', strokeWidth: 1 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
