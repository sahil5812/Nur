// src/components/MainChartPanel.jsx — Institutional Live Candlestick & Equity Canvas
import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { formatCurrency } from '../utils/currency';

function createSmoothPath(points) {
  if (!points || points.length === 0) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

// ── Native High-Definition Candlestick Canvas ──
function CandlestickView({ candles, spotPrice, ema200 }) {
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 720, height: 320 });
  const [hoveredIdx, setHoveredIdx] = useState(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setDimensions({
            width: Math.floor(entry.contentRect.width),
            height: 320
          });
        }
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const { width, height } = dimensions;
  const leftPad = 14;
  const rightPad = 58;
  const topPad = 22;
  const bottomPad = 26;

  const chartW = Math.max(100, width - leftPad - rightPad);
  const chartH = Math.max(100, height - topPad - bottomPad);

  // Price Domain Calculations
  const { minPrice, maxPrice, priceRange } = useMemo(() => {
    if (!candles || candles.length === 0) {
      return { minPrice: spotPrice - 10, maxPrice: spotPrice + 10, priceRange: 20 };
    }
    let min = Infinity;
    let max = -Infinity;
    for (const c of candles) {
      if (c.low < min) min = c.low;
      if (c.high > max) max = c.high;
      if (c.ema < min) min = c.ema;
      if (c.ema > max) max = c.ema;
      if (c.upperBand && c.upperBand > max) max = c.upperBand;
    }
    if (spotPrice < min) min = spotPrice;
    if (spotPrice > max) max = spotPrice;

    const span = Math.max(max - min, 4.0);
    const padding = span * 0.12;
    return {
      minPrice: min - padding,
      maxPrice: max + padding,
      priceRange: (max - min) + (padding * 2)
    };
  }, [candles, spotPrice]);

  const getY = (price) => {
    const ratio = (maxPrice - price) / priceRange;
    return topPad + ratio * chartH;
  };

  const getX = (index) => {
    const step = chartW / candles.length;
    return leftPad + (index + 0.5) * step;
  };

  const candleWidth = useMemo(() => {
    if (!candles.length) return 8;
    const step = chartW / candles.length;
    return Math.max(4, Math.min(14, step * 0.68));
  }, [chartW, candles.length]);

  // Points for Upper Curve & 200 EMA Baseline
  const upperPoints = useMemo(() => {
    return candles.map((c, i) => ({
      x: getX(i),
      y: getY(c.upperBand || (c.high + 1.2))
    }));
  }, [candles, maxPrice, priceRange, chartW, chartH]);

  const emaPoints = useMemo(() => {
    return candles.map((c, i) => ({
      x: getX(i),
      y: getY(c.ema || ema200)
    }));
  }, [candles, maxPrice, priceRange, chartW, chartH, ema200]);

  const upperCurvePath = useMemo(() => createSmoothPath(upperPoints), [upperPoints]);
  const emaCurvePath = useMemo(() => createSmoothPath(emaPoints), [emaPoints]);

  // Y-Axis Grid ticks (4 horizontal levels)
  const yTicks = useMemo(() => {
    const ticks = [];
    const step = priceRange / 4;
    for (let i = 0; i <= 4; i++) {
      const price = minPrice + step * i;
      ticks.push({
        price,
        y: getY(price)
      });
    }
    return ticks;
  }, [minPrice, priceRange, maxPrice, chartH]);

  // Mouse move handler
  const handleMouseMove = (e) => {
    if (!containerRef.current || !candles.length) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const step = chartW / candles.length;
    const idx = Math.floor((mouseX - leftPad) / step);
    if (idx >= 0 && idx < candles.length) {
      setHoveredIdx(idx);
    } else {
      setHoveredIdx(null);
    }
  };

  const hoveredCandle = hoveredIdx !== null && candles[hoveredIdx] ? candles[hoveredIdx] : null;
  const hoveredX = hoveredIdx !== null ? getX(hoveredIdx) : 0;
  const ySpot = getY(spotPrice);

  return (
    <div 
      ref={containerRef} 
      className="candlestick-canvas-wrapper" 
      style={{ position: 'relative', width: '100%', height: 320, overflow: 'hidden', userSelect: 'none' }}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setHoveredIdx(null)}
    >
      <svg width={width} height={height} style={{ display: 'block' }}>
        <defs>
          {/* Champagne Tan / Gold Metallic Candle Fill */}
          <linearGradient id="goldCandleGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#dfc391" />
            <stop offset="50%" stopColor="#caa469" />
            <stop offset="100%" stopColor="#ab8447" />
          </linearGradient>

          {/* Deep Charcoal / Black Candle Fill */}
          <linearGradient id="blackCandleGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#252019" />
            <stop offset="100%" stopColor="#120e0a" />
          </linearGradient>

          {/* Upper Metallic Tube Stroke Filter */}
          <filter id="upperTubeShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="1.5" floodColor="#38250f" floodOpacity="0.45" />
          </filter>
        </defs>

        {/* ── Horizontal Grid Lines & Price Labels ── */}
        {yTicks.map((t, idx) => (
          <g key={idx}>
            <line 
              x1={leftPad} 
              y1={t.y} 
              x2={width - rightPad} 
              y2={t.y} 
              stroke="rgba(140, 110, 60, 0.22)" 
              strokeDasharray="4 4" 
              strokeWidth={1} 
            />
            <text 
              x={width - rightPad + 6} 
              y={t.y + 3.5} 
              fill="#5e4c32" 
              fontSize={10} 
              fontFamily="JetBrains Mono, monospace"
              fontWeight="600"
            >
              ${Math.round(t.price)}
            </text>
          </g>
        ))}

        {/* ── Spot Price Line ── */}
        <line 
          x1={leftPad} 
          y1={ySpot} 
          x2={width - rightPad} 
          y2={ySpot} 
          stroke="#1e1b16" 
          strokeDasharray="3 3" 
          strokeWidth={1.2} 
          opacity={0.65} 
        />
        <g transform={`translate(${width - rightPad + 2}, ${ySpot - 9})`}>
          <rect width={54} height={18} fill="#1e1b16" rx={3} />
          <text 
            x={27} 
            y={12.5} 
            fill="#f5eedd" 
            fontSize={9.5} 
            fontWeight="bold" 
            textAnchor="middle" 
            fontFamily="JetBrains Mono, monospace"
          >
            ${spotPrice.toFixed(2)}
          </text>
        </g>

        {/* ── Candlesticks Rendering ── */}
        {candles.map((c, i) => {
          const cx = getX(i);
          const yH = getY(c.high);
          const yL = getY(c.low);
          const yO = getY(c.open);
          const yC = getY(c.close);
          const isBull = c.close >= c.open;
          const bodyTop = Math.min(yO, yC);
          const bodyH = Math.max(2.5, Math.abs(yC - yO));
          const w = candleWidth;

          return (
            <g key={i} className="candlestick-group">
              {/* High / Low Wick */}
              <line 
                x1={cx} 
                y1={yH} 
                x2={cx} 
                y2={yL} 
                stroke={isBull ? '#7e5d28' : '#14100c'} 
                strokeWidth={1.4} 
                strokeLinecap="round" 
              />
              {/* Candle Body */}
              <rect 
                x={cx - w / 2} 
                y={bodyTop} 
                width={w} 
                height={bodyH} 
                fill={isBull ? 'url(#goldCandleGrad)' : 'url(#blackCandleGrad)'} 
                stroke={isBull ? '#6a4c1d' : '#0c0906'} 
                strokeWidth={1} 
                rx={1.2} 
              />
            </g>
          );
        })}

        {/* ── Lower Moving Average Baseline (200 EMA) ── */}
        <path 
          d={emaCurvePath} 
          fill="none" 
          stroke="#a67c38" 
          strokeWidth={2.0} 
          strokeDasharray="4 3" 
          strokeLinecap="round" 
        />

        {/* ── Upper Metallic Contour Line (Upper Envelope / EMA Band) ── */}
        <path 
          d={upperCurvePath} 
          fill="none" 
          stroke="#543710" 
          strokeWidth={2.8} 
          filter="url(#upperTubeShadow)" 
          strokeLinecap="round" 
          strokeLinejoin="round" 
        />
        <path 
          d={upperCurvePath} 
          fill="none" 
          stroke="#946b2e" 
          strokeWidth={1.2} 
          strokeLinecap="round" 
          strokeLinejoin="round" 
          opacity={0.7} 
        />

        {/* ── Bottom Timestamp Axis ── */}
        {candles.map((c, i) => {
          if (i % 5 !== 0 && i !== candles.length - 1) return null;
          const cx = getX(i);
          return (
            <text 
              key={`t-${i}`} 
              x={cx} 
              y={height - 8} 
              fill="#6e5d42" 
              fontSize={9.5} 
              fontFamily="JetBrains Mono, monospace" 
              textAnchor="middle"
            >
              {c.time}
            </text>
          );
        })}

        {/* ── Hover Crosshairs ── */}
        {hoveredCandle && (
          <g>
            <line 
              x1={hoveredX} 
              y1={topPad} 
              x2={hoveredX} 
              y2={height - bottomPad} 
              stroke="#1e1b16" 
              strokeWidth={1} 
              strokeDasharray="2 2" 
              opacity={0.6} 
            />
            <line 
              x1={leftPad} 
              y1={getY(hoveredCandle.close)} 
              x2={width - rightPad} 
              y2={getY(hoveredCandle.close)} 
              stroke="#1e1b16" 
              strokeWidth={1} 
              strokeDasharray="2 2" 
              opacity={0.6} 
            />
          </g>
        )}
      </svg>

      {/* ── Hover Candlestick Tooltip ── */}
      {hoveredCandle && (
        <div 
          style={{
            position: 'absolute',
            left: Math.min(width - 170, Math.max(16, hoveredX - 75)),
            top: 14,
            backgroundColor: '#fbf9f4',
            border: '1.5px solid #c8a96e',
            borderRadius: 'var(--radius-sm, 6px)',
            padding: '6px 10px',
            fontSize: 10.5,
            boxShadow: '0 6px 18px rgba(70, 50, 20, 0.22)',
            pointerEvents: 'none',
            zIndex: 10
          }}
          className="mono"
        >
          <div style={{ color: '#7a6a52', fontWeight: 600, marginBottom: 2 }}>
            Time: {hoveredCandle.time}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px' }}>
            <span>O: <strong style={{ color: '#1e1b16' }}>${hoveredCandle.open?.toFixed(2)}</strong></span>
            <span>H: <strong style={{ color: '#1e1b16' }}>${hoveredCandle.high?.toFixed(2)}</strong></span>
            <span>L: <strong style={{ color: '#1e1b16' }}>${hoveredCandle.low?.toFixed(2)}</strong></span>
            <span>C: <strong style={{ color: hoveredCandle.close >= hoveredCandle.open ? '#2e7d32' : '#a83232' }}>${hoveredCandle.close?.toFixed(2)}</strong></span>
          </div>
          {hoveredCandle.ema && (
            <div style={{ color: '#9e7529', marginTop: 3, fontSize: 9.5 }}>
              EMA(200): ${hoveredCandle.ema.toFixed(2)}
            </div>
          )}
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

  // Real or synthetic candle stream for live candlestick chart
  const candleData = useMemo(() => {
    if (marketChart?.candles && marketChart.candles.length >= 5) {
      return marketChart.candles.map(c => ({
        ...c,
        open: Number(c.open || c.close),
        high: Number(c.high || Math.max(c.open || c.close, c.close) + 0.6),
        low: Number(c.low || Math.min(c.open || c.close, c.close) - 0.5),
        close: Number(c.close || c.price),
        ema: Number(c.ema || ema200),
        upperBand: Number(c.high ? c.high + 1.2 : (c.close + 2.0))
      }));
    }

    // High quality synthetic 34-candle sequence matching reference image aesthetics
    const count = 34;
    const list = [];
    const now = new Date();

    for (let i = 0; i < count; i++) {
      const dTime = new Date(now.getTime() - (count - i) * 60000);
      const timeStr = dTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

      // Wave pattern with uptrend and minor dips
      const wave = Math.sin(i * 0.32) * 3.8 + (i * 0.45);
      const open = Math.round((spotPrice - 14.0 + wave + (Math.sin(i * 1.5) * 1.2)) * 100) / 100;
      const isBull = (i % 3 !== 1);
      const bodyDelta = (Math.sin(i * 1.9) * 1.6 + 0.7) * (isBull ? 1 : -0.85);
      const close = Math.round((open + bodyDelta) * 100) / 100;
      const high = Math.round((Math.max(open, close) + Math.abs(Math.sin(i * 1.2) * 1.4) + 0.35) * 100) / 100;
      const low = Math.round((Math.min(open, close) - Math.abs(Math.cos(i * 1.4) * 1.3) - 0.25) * 100) / 100;
      const ema = Math.round((spotPrice - 15.0 + (i * 0.42)) * 100) / 100;
      const upper = Math.round((high + 1.6 + Math.sin(i * 0.4) * 0.8) * 100) / 100;

      list.push({
        time: timeStr,
        open,
        high,
        low,
        close,
        ema,
        upperBand: upper
      });
    }

    if (list.length > 0) {
      list[list.length - 1].close = spotPrice;
      list[list.length - 1].high = Math.max(list[list.length - 1].high, spotPrice + 0.4);
      list[list.length - 1].low = Math.min(list[list.length - 1].low, spotPrice - 0.4);
    }
    return list;
  }, [marketChart, spotPrice, ema200]);

  // Equity points
  const equityPoints = equityData?.points ?? [];
  const isEquityUp = (equityData?.total_pnl ?? 0) >= 0;
  const equityStroke = isEquityUp ? 'var(--green)' : 'var(--red)';

  return (
    <div className="card chart-panel-card">
      {/* ── Top Bar: Tab Switcher & Timeframe Selector ── */}
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
            <span className="telemetry-val mono" style={{ color: '#2a7b88' }}>
              ${ema200.toFixed(2)}
            </span>
          </div>

          <div className="telemetry-cell">
            <span className="telemetry-label">RSI (14)</span>
            <span 
              className="telemetry-val mono" 
              style={{ 
                color: rsi !== null 
                  ? (rsi < 36 ? 'var(--red)' : (rsi > 64 ? '#8b5cf6' : 'var(--green)')) 
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
                <span style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'rgba(168, 50, 50, 0.15)', color: 'var(--red)' }}>
                  Oversold
                </span>
              )}
              {rsi !== null && rsi > 64 && (
                <span style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'rgba(139, 92, 246, 0.15)', color: '#8b5cf6' }}>
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
          <CandlestickView 
            candles={candleData} 
            spotPrice={spotPrice} 
            ema200={ema200} 
          />
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
                <CartesianGrid stroke="rgba(140, 110, 60, 0.15)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="time" hide />
                <YAxis
                  orientation="right"
                  tick={{ fontSize: 10, fill: '#6e5d42', fontFamily: 'JetBrains Mono, monospace' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={v => `$${v}`}
                  width={56}
                />
                <Tooltip content={<EquityTooltip />} />
                <ReferenceLine y={0} stroke="rgba(140, 110, 60, 0.25)" strokeDasharray="3 3" />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke={equityStroke}
                  strokeWidth={1.8}
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
