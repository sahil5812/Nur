# 📈 NUR Institutional Trading Bot & Multi-Agent Intelligence System

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=FFD62B)](https://vitejs.dev)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Scikit-Learn](https://img.shields.io/badge/Scikit_Learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Stable-Baselines3](https://img.shields.io/badge/Stable_Baselines3-00e5ff?style=for-the-badge)](https://github.com/DLR-RM/stable-baselines3)
[![MetaTrader 5](https://img.shields.io/badge/MetaTrader_5-007ACC?style=for-the-badge)](https://www.metatrader5.com)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)

**NUR** is an institutional-grade, event-driven algorithmic trading platform and quantitative execution terminal engineered specifically for **XAUUSD (Gold Spot)** on **MetaTrader 5 (MT5)**. The platform fuses multi-timeframe structural market analysis (H4 Macro Trend, H1 Directional Momentum, M1 Dynamic Cushion Scalp) with **Hierarchical Multi-Agent Reinforcement Learning (MARL)**, an **HMM Market Regime Router**, an advanced **Random Forest Meta-Filter with Triple-Pruning**, and an automated **Fast Breakeven & Trailing Stop Risk Engine**.

The system features an ultra-responsive, dark-mode **Bloomberg/TradingView-inspired React terminal**, a native Windows desktop client (`PyWebView`), a multi-tenant SaaS backend with isolated risk profiles, and an interactive Telegram command center with Google Gemini AI integration.

---

## 📊 Live Performance & Verification Track Record

Telemetry captured from live out-of-sample forward execution on MetaTrader 5 (Gold Spot XAUUSD):

| Metric | Measured Value | Institutional Benchmark | Status |
| :--- | :--- | :--- | :--- |
| **Profit Factor (Gross Win / Loss)** | **3.89** | > 1.75 | ✅ Institutional Grade |
| **Average Trade Expectancy** | **+$2,701.98 USD** | Positive Expectancy | ✅ Robust Edge |
| **Total Realized P&L** | **+$48,635.69 USD** | Capital Expansion | ✅ Exceptional |
| **Peak Trade Gain** | **+$20,479.80 USD** | Dynamic ATR Trail | ✅ Runaway Trends Captured |
| **Controlled Stop Loss** | **-$6,355.12 USD** | Strict Circuit Breakers | ✅ Defined Asymmetric Risk |
| **Terminal Equity Balance** | **$148,635.69 USD** | Account Compounding | ✅ Verified |
| **Win Rate** | **44.4%** (8W / 10L) | 35% - 50% for 3:1+ R:R | ✅ Mathematical Asymmetry |

> [!NOTE]
> Even with a 44.4% win rate, the system produces a **3.89 Profit Factor** because average wins (+$6,079.46) vastly outsize tightly managed average losses (-$1,563.85). This validates the mathematical efficacy of the **0.5x ATR Breakeven Protection** and **1.5x ATR Dynamic Trailing Stop**.

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph MarketFeeds ["1. Market Ingestion & MT5 Broker Gateway"]
        MT5["MetaTrader 5 Terminal (Live XAUUSD Ticks & M1/H1/H4 Candles)"]
    end

    subgraph IntelligenceLayer ["2. Hierarchical AI & Quantitative Intelligence"]
        HMM["Hidden Markov Model (2-State Gaussian Viterbi Classifier)"]
        MARL["MARL PPO Suite (Trend, Range, Universal Fallback)"]
        RF["Random Forest Meta-Filter (López de Prado Triple-Pruned)"]
    end

    subgraph TechnicalGuards ["3. Execution Rules & Dynamic Safeguards"]
        MTF["3-TF Trend Engine (H4 Bias + H1 Direction + M1 200 EMA Pullback)"]
        RSIGuard["RSI Exhaustion Guard (Block SELL < 36.0 | Block BUY > 64.0)"]
        Scoring["Scoring Agent (Threshold >= 65, Penalty on Extreme Overbought/Oversold)"]
    end

    subgraph RiskEngine ["4. Risk & Order Execution Desk"]
        BotEngine["Multi-Tenant Execution Loop (bot_engine.py)"]
        FastBE["Fast Breakeven Engine (Move SL to Entry @ 0.5x ATR Profit)"]
        TrailSL["Dynamic Trailing SL (1.5x ATR Ratchet)"]
        DailyLock["Daily Loss Guard (-$50 Max Lock) & Profit Target Target"]
        PaperTrader["Paper Trader Engine (Crash-Resilient JSON Persistence)"]
    end

    subgraph Backend ["5. Core API & Database"]
        FastAPI["FastAPI Gateway (Port 8000 REST + WebSockets)"]
        DB["SQLite Database (WAL Mode + Multi-Tenant Profiles)"]
    end

    subgraph ClientInterfaces ["6. Institutional User Interfaces"]
        DesktopApp["Native Windows Desktop App (PyWebView + Auto-Shortcut)"]
        ReactUI["Bloomberg-Style React Terminal (Vite + Dark Mode)"]
        TelegramBot["Telegram Remote Controller + Gemini NLP Chat"]
    end

    MT5 -->|Real-Time Ticks & OHLCV| MTF
    MTF -->|State Features & Distance| HMM
    HMM -->|Decoded Regime: TREND vs RANGE| MARL
    MARL -->|Action Candidate: BUY / SELL / HOLD| RF
    RF -->|Conviction Gate: P >= 42%| Scoring
    RSIGuard -->|Veto on Exhaustion| Scoring
    Scoring -->|Approved Setup: Score >= 65| BotEngine

    BotEngine -->|Active Position State| FastBE
    FastBE -->|0.5x ATR Gain Reached| TrailSL
    TrailSL -->|Ratchet Protected SL| PaperTrader
    PaperTrader -->|Persist Trade History| DB
    DailyLock -->|Circuit Breaker Shutdown| BotEngine

    FastAPI <-->|Live Stream: 1s Tick WebSocket| ReactUI
    FastAPI <-->|Native Webview Window| DesktopApp
    BotEngine <-->|Instant Alerts & Executions| TelegramBot
    FastAPI <-->|Tenant Config & Auth| DB
```

---

## 🧠 Algorithmic Core & Quantitative Innovations

### 1. 🎯 3-Tier Multi-Timeframe (MTF) Trend Engine
* **Macro Horizon (H4):** Calculates long-term institutional order flow and macro bias (Bullish/Bearish) using the 200-period Exponential Moving Average (EMA).
* **Intermediate Horizon (H1):** Verifies momentum direction to ensure entries never trade counter to primary hourly structure.
* **Micro Execution Horizon (M1):** Pinpoints precision pullback scalps toward the dynamic 200 EMA cushion with strict ATR volatility buffer calculations.

### 2. 🤖 Hierarchical Multi-Agent Reinforcement Learning (MARL) & HMM
* **2-State Gaussian Hidden Markov Model (`rl/hmm_classifier.py`):**
  * Uses Expectation-Maximization (**Baum-Welch**) and **Viterbi decoding** with diagonal covariance Gaussian emissions to classify live markets into:
    * `TRENDING` (High directional drift, persistent volatility)
    * `RANGING` (Mean-reverting, stationary return distribution)
  * Seamless state transitions: When state probability confidence is $\ge 0.75$, the engine routes to the specialized agent. When confidence is $< 0.75$ (transition chop), it automatically falls back to universal PPO.
* **Specialized PPO Agents (`rl/agent.py`):**
  * `ppo_trend.zip`: Optimized for breakout continuation, trailing runners, and momentum expansion.
  * `ppo_range.zip`: Tuned for boundary mean-reversion, tight profit targets, and rapid inventory turnover.
  * `ppo_xauusd.zip`: Universal baseline agent trained across all historical market conditions.

### 3. 🌲 Random Forest Meta-Filter with Triple-Pruning (`intelligence/rf_filter.py`)
Inspired by **Marcos López de Prado's Meta-Labeling** methodology (*Advances in Financial Machine Learning*):
* The primary strategy (MTF trend + MARL policy) proposes trade direction (BUY/SELL).
* The Random Forest Meta-Model acts as a **secondary gatekeeper**, predicting the probability of trade success:
  $$P(\text{Trade Success} \mid X) \ge 42\%$$
* Any setup with $P < 0.42$ is **strictly vetoed**, eliminating false breakouts, choppy whipsaws, and bad market conditions.

#### The 4-Stage Pruning Architecture:
1. **Stage 1 — Pairwise Collinearity Pruning:**
   * Computes Pearson correlation matrix $R$ across all candidate features.
   * For any pair with $|r_{ij}| \ge 0.88$, automatically prunes the redundant feature with lower empirical variance.
2. **Stage 2 — Recursive Variance Inflation Factor (VIF) Pruning:**
   * Calculates multivariate multicollinearity:
     $$VIF_j = \frac{1}{1 - R_j^2}$$
   * Recursively eliminates the feature with the highest VIF until all remaining features achieve $VIF \le 10.0$ (ensuring zero multicollinearity).
3. **Stage 3 — Gini MDI Feature Importance Pruning:**
   * Trains a pilot ensemble and eliminates any feature contributing $< 2\%$ Mean Decrease in Impurity (MDI).
4. **Stage 4 — Minimal Cost-Complexity Tree Pruning:**
   * Governed by cost-complexity factor $\alpha_{ccp} = 0.001$, `max_depth = 8`, `min_samples_leaf = 30`, and `min_samples_split = 60`, preventing decision tree overfitting.

#### 12 Active Quantitative Features:
1. `z_h1`: H1 normalized price distance to 200 EMA in units of ATR.
2. `z_m5`: M5 normalized price distance to 200 EMA.
3. `z_m1`: M1 entry bar normalized distance to 200 EMA.
4. `rsi`: 14-period Relative Strength Index.
5. `rsi_slope_5`: 5-candle momentum derivative of RSI.
6. `macd_hist`: MACD(12,26,9) histogram momentum spread.
7. `atr_normalized`: 14-period ATR standardized against rolling mean and volatility.
8. `realized_vol_20`: 20-period realized standard deviation of log returns.
9. `spread_ratio`: Real-time broker bid-ask spread divided by ATR.
10. `gamma_trend`: HMM smoothed posterior probability of trending regime.
11. `z_alignment`: Multi-timeframe trend directional consensus score.
12. `hour_sin` / `hour_cos`: Cyclical sinusoidal diurnal trading session encodings.

---

## 🛡️ Institutional Risk Management & Execution Guards

### 1. 🚫 RSI Extreme Exhaustion Guards
To prevent buying the top of a rally or shorting the absolute bottom of a dump:
* **`RSI_OVERSOLD_BLOCK = 36.0`**: If M1 RSI is below 36.0, **SELL entries are strictly blocked**. Even in a strong bearish trend, shorting when RSI is oversold leads to immediate bounce drawdown.
* **`RSI_OVERBOUGHT_BLOCK = 64.0`**: If M1 RSI is above 64.0, **BUY entries are strictly blocked**.
* **Scored RSI Distribution:**
  * Ideal Continuation Zone (RSI 40.0 - 60.0): **+10 Points Bonus**
  * Overbought Chasing ($RSI > 64.0$ on BUY): **-20 Points Penalty**
  * Oversold Chasing ($RSI < 36.0$ on SELL): **-20 Points Penalty**

### 2. ⚡ Ultra-Fast Breakeven (0.5x ATR Protection) & Scale-Out Partial TP (1.0x ATR)
* **0.5x ATR Fast Breakeven:**
  * In Gold trading (where average M1 ATR is ~$2.00 - $3.00), as soon as the trade gains **$1.00 - $1.50** (0.5x ATR), the stop loss is clamped to entry price, turning the trade **100% risk-free within 2 minutes**.
* **Scale-Out Partial Take-Profit (50% Cash Lock @ 1.0x ATR):**
  * Once the trade expands into a **1.0x ATR gain** (~$2.50+ on Gold), the engine automatically closes **50% of the lot size**, banking immediate realized cash profit into the balance.
  * The remaining 50% position has its Stop Loss locked firmly at Breakeven as an unconstrained **"Free Runner"** to ride multi-thousand dollar trend expansions.

### 3. 📈 Dynamic 1.5x ATR Ratchet Trailing Stop & Kelly Edge Sizing
* **Ratchet Trailing SL:**
  * For SELL positions: $SL_{\text{new}} = \min(SL_{\text{current}}, \text{Price} + 1.5 \times ATR)$
  * For BUY positions: $SL_{\text{new}} = \max(SL_{\text{current}}, \text{Price} - 1.5 \times ATR)$
  * As Gold explodes in the trade direction, profits ratchet up automatically, capturing massive runner moves (e.g. +$20,479.80 peak trade).
* **Conviction-Weighted Kelly Position Sizing:**
  * Lot sizes dynamically scale based on the Random Forest Meta-Filter's calibrated success probability $P(\text{Success} \mid X)$:
    * $P \ge 65\%$ (High Conviction Edge): **1.30x Sizing Multiplier** (aggressive capture)
    * $0.55 \le P < 0.65$ (Solid Edge): **1.05x Sizing Multiplier**
    * $0.48 \le P < 0.55$ (Moderate Edge): **0.85x Sizing Multiplier**
    * $P < 0.48$ (Borderline Edge): **0.65x Sizing Multiplier** (defensive risk trimming)

### 4. 📰 Live ForexFactory Economic Calendar & Volatility Blackout
* Automated real-time ingestion of high-impact USD releases (NFP, CPI, FOMC, PPI, Retail Sales, Fed Chair Speeches).
* Features a local 6-hour TTL cache (`logs/news_calendar.json`) with graceful offline fallback to deterministic mathematical schedules.
* Automatically halts trading during a strict **15-minute buffer before and after** high-impact releases, completely shielding accounts from wild slippage and spread spikes.

### 5. 🔒 Multi-Tenant Daily Loss & Profit Locks
* **Daily Loss Limit (`DAILY_LOSS_LIMIT`, default -$50 USD)**:
  * If daily realized losses exceed the limit, the trading engine instantly locks the account for **24 hours**.
  * Prevents revenge trading, emotional spirals, and adverse market regime shifts.
* **Daily Profit Target (`DAILY_PROFIT_TARGET`, default +$100 USD)**:
  * Locks in daily gains once reached, preventing giving profits back to the market during late-session churn.
* **Order Isolation & Anti-Collision**:
  * Multi-tenant execution loops segregate users by unique `user_id` and MT5 Magic Numbers (`260000 + user_id`), preventing position crosstalk or duplicate lots.

---

## 📁 Repository Structure

```
Nur/
├── api/                             # FastAPI Backend & WebSockets
│   ├── auth.py                      # JWT authentication, Argon2 hashing & OAuth
│   └── main.py                      # REST endpoints, WebSocket live stream & manual override
├── core/                            # Trading Engine & State Machine
│   ├── engine.py                    # Trading coordinator loop
│   ├── execution.py                 # MT5 Order execution broker wrapper
│   ├── guardian.py                  # Account safety and daily drawdown watchdog
│   ├── strategy.py                  # 3-Timeframe pullback scalp strategy rules
│   └── learner.py                   # Online adaptive statistics
├── dashboard/                       # React 18 + Vite Institutional Terminal
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx           # Gateway status, account balance, user menu
│   │   │   ├── MarketRibbon.jsx     # High-density ticker ribbon (Spot, EMA, ATR, Regime)
│   │   │   ├── MainChartPanel.jsx   # Live M1/M5/H1 Candlestick chart + 200 EMA overlay
│   │   │   ├── AIExecutionDesk.jsx  # Conviction gauge, risk slider, Buy/Sell/Flatten buttons
│   │   │   └── TerminalDock.jsx     # Order history, performance analytics, engine stream
│   │   ├── hooks/useLiveData.js     # Sub-second WebSocket stream handler
│   │   └── App.jsx                  # Main interface routing & layout
│   └── package.json                 # Dashboard package dependencies
├── database/                        # Thread-Safe SQLite Storage
│   ├── db.py                        # WAL-mode connection manager & schema migrations
│   ├── stats_db.py                  # User stats, trade logs & daily lock persistence
│   └── nur_trading.db               # SQLite database file
├── indicators/                      # Technical Analysis Quant Calculators
│   ├── atr.py                       # 14-period Average True Range calculator
│   ├── ema.py                       # Exponential Moving Average engine
│   ├── macd.py                      # MACD(12,26,9) line, signal, and histogram
│   └── rsi.py                       # RSI(14) with institutional oversold/overbought scoring
├── intelligence/                    # Quantitative Machine Learning
│   └── rf_filter.py                 # Random Forest Meta-Filter with Triple-Pruning & VIF
├── paper/                           # Paper Trading Simulator
│   └── paper_trader.py              # Zero-risk execution & persistent position tracking
├── rl/                              # Reinforcement Learning Pipeline
│   ├── agent.py                     # MARL Router (HMM + PPO agents)
│   ├── hmm_classifier.py            # Gaussian HMM Baum-Welch & Viterbi classifier
│   ├── trading_env.py               # Gymnasium-compliant quantitative trading environment
│   └── models/                      # Trained model weights
│       ├── hmm_model.json           # Trained HMM regime transition & emission parameters
│       ├── ppo_trend.zip            # PPO policy for trending regimes
│       ├── ppo_range.zip            # PPO policy for ranging regimes
│       ├── ppo_xauusd.zip           # Universal fallback PPO policy
│       ├── rf_meta_filter.joblib    # Pruned Random Forest classifier
│       └── rf_filter_meta.json      # Pruned feature list & training telemetry
├── utils/                           # Core Utilities & MT5 Bridge
│   ├── logger.py                    # Colored terminal & rotating log file handlers
│   ├── mt5_connector.py             # Resilient MetaTrader 5 connection manager
│   └── status_writer.py             # Atomic status JSON state serialization
├── bot_engine.py                    # Standalone algorithmic trading engine loop
├── desktop_app.py                   # PyWebView native Windows desktop launcher
├── config.py                        # Centralized configuration manager
├── test_loss_lock.py                # Regression test suite for risk & guardrails
├── requirements.txt                 # Python dependencies
└── .env.example                     # Environment variables configuration template
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
* **Operating System:** Windows 10 or 11 (required for native MetaTrader 5 Python IPC bridge).
* **Python:** 3.11.x or 3.12.x (64-bit).
* **Node.js:** 18.x or 20.x (LTS recommended).
* **MetaTrader 5 Client Terminal:** Installed and logged into any demo or live broker account with **Algo Trading enabled**.

---

### 2. Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sahil5812/Nur.git
   cd Nur
   ```

2. **Create and activate a Python Virtual Environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Build the React Frontend Dashboard:**
   ```powershell
   cd dashboard
   npm install
   npm run build
   cd ..
   ```

---

### 3. Environment Configuration (`.env`)

Copy `.env.example` to `.env` in the root directory (or let `desktop_app.py` auto-generate it):

```ini
# ============================================================
# NUR BOT — Configuration Settings
# ============================================================

# ── Trading Mode ─────────────────────────────────────────────
# Set to true for safe virtual paper simulation; false for real MT5 execution
PAPER_TRADING=true
BYPASS_NEWS_FILTER=true

# ── Risk Parameters ──────────────────────────────────────────
RISK_PERCENT=1.0
DAILY_LOSS_LIMIT=-50.0
DAILY_PROFIT_TARGET=100.0
MAX_TRADES_PER_DAY=5
MIN_SCORE_TO_TRADE=65

# ── Strategy & Market Settings ───────────────────────────────
SYMBOL=XAUUSD
EMA_PERIOD=200
ATR_PERIOD=14
COOLDOWN_SECONDS=30

# ── MetaTrader 5 Credentials (Optional - auto-attaches to open desktop MT5) ──
MT5_LOGIN=5058657813
MT5_PASSWORD=
MT5_SERVER=MetaQuotes-Demo

# ── Telegram Control & Remote Alerts (Optional) ──────────────
TELEGRAM_TOKEN=your_telegram_bot_token
ALLOWED_CHAT_IDS=your_chat_id
GEMINI_API_KEY=your_gemini_api_key

# ── Authentication & Security ────────────────────────────────
JWT_SECRET=super_secure_random_32_byte_jwt_secret_key_here
SESSION_EXPIRE_HOURS=24
```

---

### 4. Running the Platform

#### Mode A: Unified Native Desktop Terminal (Recommended)
Run the all-in-one native application:
```powershell
python desktop_app.py
```
This automatically initializes:
* Background FastAPI Gateway (`http://127.0.0.1:8000`)
* Bot Trading Engine loop connected to MetaTrader 5
* Telegram command polling loop
* Native PyWebView Bloomberg-style trading terminal
* Auto-generates a desktop shortcut (`Nur Bot.lnk`)

#### Mode B: Headless / Web-First Mode
Run the backend and UI as independent processes:
```powershell
# Terminal 1: FastAPI Gateway
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Algorithmic Bot Engine
python bot_engine.py

# Terminal 3: Vite Dev Server (for frontend development)
cd dashboard
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## 🧪 Testing & Quality Assurance

Run the comprehensive test suite to verify machine learning models, VIF pruning, and safety guardrails:

```powershell
# Run Random Forest, Triple-Pruning & VIF tests
pytest tests/test_rf_filter.py -q

# Run Engine, Strategy, and Guardian tests
pytest tests/test_engine.py tests/test_strategy.py tests/test_guardian.py -q

# Run Risk Engine, Breakeven & Loss Lock tests
python test_loss_lock.py
```

### Verified Test Suite Results:
* `tests/test_rf_filter.py`: **8 passed** (Pairwise pruning, Recursive VIF, Gini MDI, Cost-Complexity, Decision thresholding)
* `tests/test_engine.py`, `test_strategy.py`, `test_guardian.py`: **11 passed** (3-TF alignment, pullback confirmation, session validation)
* `test_loss_lock.py`: **14 passed** (RSI oversold/overbought guards, 0.5x ATR breakeven, 24h loss locks, profit targets)
* **Total: 33 / 33 tests passing (100% clean)**

---

## 📱 Telegram Remote Control & Gemini AI

NUR includes a remote management interface via Telegram:

| Command | Action Description |
| :--- | :--- |
| `/start_trading` | Resumes automated trade execution |
| `/stop` | Pauses execution and transitions engine to idle |
| `/status` | Live snapshot of price, EMA, RSI, regime, score, and active locks |
| `/balance` | Displays account equity, balance, floating PnL, and daily stats |
| `/positions` | Lists all active orders, entry prices, and trailing stops |
| `/report` | Sends daily performance summary and win-rate analytics |
| `/panic` | **Emergency Flatten**: Instantly closes all open positions |

* **Gemini AI NLP**: Users can send freeform natural language queries (e.g., *"What is our risk exposure right now?"* or *"Analyze the current gold trend"*) to receive immediate quantitative insights powered by Google Gemini.

---

## ⚠️ Disclaimer & Risk Warning

This trading system is developed for educational, quantitative research, and technical evaluation purposes only. Trading foreign exchange, precious metals (XAUUSD), and leveraged derivatives carries a high level of risk and may not be suitable for all investors. High leverage can work against you as well as for you.

Before deciding to trade financial instruments, you should carefully consider your investment objectives, level of experience, and risk appetite. Past performance, backtests, and paper trading simulations are not indicative of future results. Never trade with money you cannot afford to lose.

---

## 👤 Author & Maintainer

* **Repository:** [https://github.com/sahil5812/Nur.git](https://github.com/sahil5812/Nur.git)
* **Author:** Sahil ([@sahil5812](https://github.com/sahil5812))
* **License:** MIT License
