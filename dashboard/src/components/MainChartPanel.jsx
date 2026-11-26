// src/components/MainChartPanel.jsx — Institutional Live Market & Equity Canvas
import React, { useState, useEffect, useMemo } from 'react';
import {
  AreaChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { formatCurrency, getCurrencySymbol } from '../utils/currency';

function MarketTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      backgroundColor: '#f9f6ee',
      border: '1px solid #c8a96e',
      borderRadius: 'var(--radius-sm)',
      padding: '8px 12px',
      fontSize: 11,
      boxShadow: '0 8px 24px rgba(70, 50, 20, 0.18)'
    }}>
      <div style={{ color: '#7c6e57', marginBottom: 4 }}>
        {d.time || label}
      </div>
      <div style={{ color: '#1e1b16', fontWeight: 600 }} className="mono">
        Price: ${Number(d.close || d.price).toFixed(2)}
      </div>
      {d.ema && (
        <div style={{ color: '#a67c38', fontSize: 10, marginTop: 2 }} className="mono">
          EMA(200): ${Number(d.ema).toFixed(2)}
        </div>
      )}
      {d.high && (
        <div style={{ color: '#7c6e57', fontSize: 10, marginTop: 2 }} className="mono">
          H: ${Number(d.high).toFixed(2)} · L: ${Number(d.low).toFixed(2)}
        </div>
      )}
    </div>
  );
}

function EquityTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      backgroundColor: '#f9f6ee',
      border: '1px solid #c8a96e',
      borderRadius: 'var(--radius-sm)',
      padding: '8px 12px',
      fontSize: 11,
      boxShadow: '0 8px 24px rgba(70, 50, 20, 0.18)'
    }}>
      <div style={{ color: '#7c6e57', marginBottom: 4 }}>
        {d.time ? new Date(d.time).toLocaleTimeString() : label}
      </div>
      <div style={{ color: d.equity >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }} className="mono">
        Cumulative: ${d.equity?.toFixed(2)}
      </div>
      {d.pnl !== undefined && (
        <div style={{ color: d.pnl >= 0 ? 'var(--green)' : 'var(--red)', fontSize: 10, marginTop: 2 }} className="mono">
          Trade P&L: {d.pnl >= 0 ? '+' : ''}${d.pnl?.toFixed(2)}
        </div>
      )}
    </div>
  );
}

export default function MainChartPanel({ engine, equityData, marketChart, loading = false, stats }) {
  const [activeTab, setActiveTab] = useState('market'); // 'market' | 'equity'
  const [timeframe, setTimeframe] = useState('M1');

  const currency = stats?.currency || 'INR';
  const baselineBalance = stats?.balance ?? 5000.0;
  const spotPrice = engine?.last_close ? Number(engine.last_close) : (marketChart?.current_price ? Number(marketChart.current_price) : 3565.20);
  const ema200 = engine?.ema200 ? Number(engine.ema200) : 3568.50;
  const atr = engine?.atr ? Number(engine.atr) : 2.14;
  const spread = engine?.spread !== undefined ? Number(engine.spread) : 0.20;
  const rsi = engine?.rsi !== undefined && engine?.rsi !== null ? Number(engine.rsi) : null;

  // Real or synthetic candle stream for live chart
  const candleData = useMemo(() => {
    if (marketChart?.candles && marketChart.candles.length >= 5) {
      return marketChart.candles;
    }
    // Fallback: build a gentle 30-point sequence leading to current spot
    const points = [];
    const base = spotPrice;
    for (let i = 29; i >= 0; i--) {
      const offset = (Math.sin(i * 0.4) * 1.8) - (i * 0.08);
      const close = Math.round((base - offset) * 100) / 100;
      points.push({
        time: `${20 - Math.floor(i / 2)}:${(60 - (i % 2) * 30).toString().padStart(2, '0')}`,
        close: close,
        high: close + 0.6,
        low: close - 0.5,
        ema: Math.round((ema200 - offset * 0.5) * 100) / 100
      });
    }
    return points;
  }, [marketChart, spotPrice, ema200]);

  // Equity points
  const equityPoints = equityData?.points ?? [];
  const isEquityUp = (equityData?.total_pnl ?? 0) >= 0;
  const equityStroke = isEquityUp ? 'var(--green)' : 'var(--red)';

  return (
    <div className="card chart-panel-card">
      {/* ── Top Bar: Tab Switcher & Live Ticker Strip ── */}
      <div className="chart-header">
        <div className="chart-tabs">
          <button
            type="button"
            className={`chart-tab-btn ${activeTab === 'market' ? 'active' : ''}`}
            onClick={() => setActiveTab('market')}
          >
            Live Market ({marketChart?.symbol || 'XAUUSDm'})
          </button>
          <button
            type="button"
            className={`chart-tab-btn ${activeTab === 'equity' ? 'active' : ''}`}
            onClick={() => setActiveTab('equity')}
          >
            Equity Trajectory
          </button>
        </div>

        {activeTab === 'market' && (
          <div className="timeframe-selector">
            {['M1', 'M5', 'H1'].map((tf) => (
              <button
                key={tf}
                type="button"
                className={`tf-chip ${timeframe === tf ? 'active' : ''}`}
                onClick={() => setTimeframe(tf)}
              >
                {tf}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Secondary Subheader: Live Indicator Telemetry ── */}
      {activeTab === 'market' ? (
        <div className="chart-telemetry-bar">
          <div className="telemetry-cell">
            <span className="telemetry-label">Spot Close</span>
            <span className="telemetry-val mono" style={{ color: 'var(--green)' }}>
              ${spotPrice.toFixed(2)}
              <span className="live-pulse-dot" />
            </span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">200 EMA</span>
            <span className="telemetry-val mono" style={{ color: '#38bdf8' }}>
              ${ema200.toFixed(2)}
            </span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">RSI (14)</span>
            <span 
              className="telemetry-val mono" 
              style={{ 
                color: rsi !== null 
                  ? (rsi < 36 ? 'var(--red)' : (rsi > 64 ? '#c084fc' : 'var(--green)')) 
                  : 'var(--text-1)',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4
              }}
              title={rsi !== null ? (rsi < 36 ? 'Oversold (<36) — SELL blocked' : (rsi > 64 ? 'Overbought (>64) — BUY blocked' : 'Normal Momentum')) : 'RSI Momentum'}
            >
              {rsi !== null ? rsi.toFixed(1) : '—'}
              {rsi !== null && rsi < 36 && (
                <span style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'rgba(239, 68, 68, 0.2)', color: 'var(--red)' }}>
                  Oversold
                </span>
              )}
              {rsi !== null && rsi > 64 && (
                <span style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'rgba(192, 132, 252, 0.2)', color: '#c084fc' }}>
                  Overbought
                </span>
              )}
            </span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">ATR (14)</span>
            <span className="telemetry-val mono">
              ${atr.toFixed(2)}
            </span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">Spread</span>
            <span className="telemetry-val mono">
              ${spread.toFixed(2)}
            </span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">Bias</span>
            <span className="telemetry-val" style={{ color: engine?.h1_trend?.includes('BULL') ? 'var(--green)' : (engine?.h1_trend?.includes('BEAR') ? 'var(--red)' : 'var(--text-2)') }}>
              {engine?.h1_trend || 'Neutral'}
            </span>
          </div>
        </div>
      ) : (
        <div className="chart-telemetry-bar">
          <div className="telemetry-cell">
            <span className="telemetry-label">Realized Net P&L</span>
            <span className={`telemetry-val mono ${isEquityUp ? 'positive' : 'negative'}`}>
              {formatCurrency(equityData?.total_pnl ?? 0, currency, true)}
            </span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">Baseline Watermark</span>
            <span className="telemetry-val mono">{formatCurrency(baselineBalance, currency)}</span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">Closed Executions</span>
            <span className="telemetry-val mono">{equityPoints.length}</span>
          </div>
        </div>
      )}

      {/* ── Main Canvas ── */}
      <div className="chart-canvas-container">
        {activeTab === 'market' ? (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={candleData} margin={{ top: 12, right: 12, bottom: 4, left: 4 }}>
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#a67c38" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#a67c38" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(140, 110, 60, 0.15)" strokeDasharray="3 3" vertical={false} />
              <XAxis 
                dataKey="time" 
                tick={{ fontSize: 10, fill: '#6e5d42', fontFamily: 'JetBrains Mono, monospace' }}
                axisLine={{ stroke: 'rgba(140, 110, 60, 0.25)' }}
                tickLine={false}
              />
              <YAxis
                domain={['auto', 'auto']}
                orientation="right"
                tick={{ fontSize: 10, fill: '#6e5d42', fontFamily: 'JetBrains Mono, monospace' }}
                tickLine={false}
                axisLine={{ stroke: 'rgba(140, 110, 60, 0.25)' }}
                tickFormatter={v => `$${Math.round(v)}`}
                width={56}
              />
              <Tooltip content={<MarketTooltip />} />
              <ReferenceLine y={spotPrice} stroke="#1e1b16" strokeDasharray="3 3" opacity={0.5} />
              <ReferenceLine y={ema200} stroke="#a67c38" strokeDasharray="4 4" opacity={0.8} />
              
              <Area
                type="monotone"
                dataKey="close"
                stroke="#1e1b16"
                strokeWidth={2.0}
                fill="url(#priceFill)"
                dot={false}
                activeDot={{ r: 4, fill: '#a67c38', stroke: '#1e1b16', strokeWidth: 1.5 }}
              />
              <Line
                type="monotone"
                dataKey="ema"
                stroke="#a67c38"
                strokeWidth={2.0}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          equityPoints.length === 0 ? (
            <div className="chart-empty-state">
              <div className="empty-title">Baseline Capital: {formatCurrency(baselineBalance, currency)} Active</div>
              <div className="empty-sub">
                Equity curve will record real-time trajectory as soon as closed trades complete.
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={equityPoints} margin={{ top: 12, right: 12, bottom: 4, left: 4 }}>
                <defs>
                  <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={equityStroke} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={equityStroke} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(238, 240, 245, 0.04)" vertical={false} />
                <XAxis dataKey="time" hide />
                <YAxis
                  orientation="right"
                  tick={{ fontSize: 10, fill: 'var(--text-3)', fontFamily: 'JetBrains Mono, monospace' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={v => `$${v}`}
                  width={56}
                />
                <Tooltip content={<EquityTooltip />} />
                <ReferenceLine y={0} stroke="rgba(238, 240, 245, 0.1)" strokeDasharray="3 3" />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke={equityStroke}
                  strokeWidth={1.6}
                  fill="url(#eqFill)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )
        )}
      </div>
    </div>
  );
}
