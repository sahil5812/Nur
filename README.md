# 📈 NUR Trading Bot Dashboard & ML Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=FFD62B)](https://vitejs.dev)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Stable-Baselines3](https://img.shields.io/badge/Stable_Baselines3-00e5ff?style=for-the-badge)](https://github.com/DLR-RM/stable-baselines3)
[![MetaTrader 5](https://img.shields.io/badge/MetaTrader_5-007ACC?style=for-the-badge)](https://www.metatrader5.com)

**NUR** is a production-grade, event-driven multi-tenant SaaS algorithmic trading engine designed for XAUUSD (Gold) trading on MetaTrader 5. It integrates a live execution engine, a reinforcement learning (PPO) training/evaluation pipeline, a responsive React-based management dashboard, a Telegram command center with Gemini AI integration, and standalone mobile app installers (PWA/Android).

---

## 🛠️ System Architecture

```mermaid
graph TD
    subgraph Frontend ["Client UI"]
        ReactDash["React Web Dashboard (Port 5173)"]
        PWAMobile["Installable PWA App"]
        CapAndroid["Native Android APK (Capacitor)"]
    end

    subgraph Backend ["FastAPI Server (Port 8000)"]
        FastAPI["FastAPI API Gateway"]
        WSHandler["WebSocket Live Stream Handler"]
        AuthHandler["Auth Handler (JWT, OAuth, One Tap)"]
    end

    subgraph CoreEngine ["Trading & AI Orchestration"]
        BotEngine["SaaS Bot Engine (main.py)"]
        RLAgent["PPO Reinforcement Learning Agent"]
        MT5["MetaTrader 5 Client Terminal"]
    end

    subgraph Database ["Storage & APIs"]
        SQLite["SQLite WAL Database (trading.db)"]
    end

    subgraph Messaging ["Alerts & Interactive AI"]
        Telegram["Telegram Bot (integrations/telegram_bot.py)"]
        Gemini["Gemini AI Natural Language Chat"]
    end

    ReactDash <-->|HTTP/REST & WebSockets| FastAPI
    PWAMobile <-->|HTTP/REST & WebSockets| FastAPI
    CapAndroid <-->|HTTP/REST & WebSockets| FastAPI
    
    FastAPI <--> SQLite
    FastAPI -->|Manual Commands| SQLite
    
    BotEngine <-->|Polls Manual Commands| SQLite
    BotEngine -->|MT5 API Calls| MT5
    BotEngine -->|Observations| RLAgent
    
    Telegram <-->|Polling & Alerts| BotEngine
    Telegram <-->|NLP Queries| Gemini
```

---

## ✨ Core Features

### 1. Multi-Tenant SaaS Engine
*   **User Isolation**: Dynamic loading of tenant configurations, risk multipliers, credentials (MT5 logins), and statistics. *Multi-tenant architecture is pre-configured, currently running in optimized single-user local mode for demo validation.*
*   **Multi-tenant Database Schema**: SQLite database running in **WAL (Write-Ahead Logging)** mode for concurrent high-speed reads/writes without trade locking.

### 2. Premium Real-Time React Dashboard
*   **WebSocket Stream**: Instant updates (1-second updates) of floating equity, balance, active trades list, and trading metrics.
*   **Interactive Control Panel**: Start/stop trading loops, adjust risk multipliers on the fly, and send forced manual orders (`BUY`, `SELL`, `CLOSE ALL`).
*   **Google One Tap Login**: Modern, zero-click authentication with real Google Identity JWT credential validation.

### 3. Machine Learning (PPO) Pipeline
*   **Custom Gym Environment**: Custom Gymnasium-compliant environment (`XAUUSDTradingEnv`) with normalized observation parameters (RSI, MACD, EMA distance, normalized ATR, London/NY/Asian sessions).
*   **History Fetcher**: Chunk-based historical XAUUSD data downloader to prevent API timeouts.
*   **Train/Val/Test Splits**: Rigorous evaluation pipeline splitting data into 70% Train, 15% Validation, and 15% Test datasets to prevent overfitting.
*   **Validation check**: Automatic post-training validation phase evaluating model generalisation on unseen validation curves.
*   **True Evaluation**: Runs deterministic out-of-sample evaluations on test splits and saves equity curve plots.

### 4. Installable Mobile Application (PWA / Android APK)
*   **Progressive Web App (PWA)**: Full manifest, offline caching, and standalone browser app installers for Android and iOS.
*   **Native Android Project**: Pre-configured Capacitor integration in `dashboard/android/` for compilation to native Android APKs.

### 5. Telegram Commands & Gemini AI Chat
*   **Interactive Controls**: Run remote commands: `/start_trading`, `/stop`, `/status`, `/balance`, `/positions`, `/report`, and `/panic` (emergency close all).
*   **Gemini Chat**: Ask the bot questions about system health, current trades, and performance reports in plain Hinglish or English using Gemini AI.

---

## 📁 Repository Layout

```
Nur-main/
├── api/                   # FastAPI Backend Routing
│   ├── auth.py            # OAuth, Google One Tap, JWT endpoints
│   └── main.py            # API Gateway endpoints, WebSocket streams
├── core/                  # Core Algorithmic trading components
│   ├── engine.py          # Trading loop coordinator
│   ├── strategy.py        # Trend/pullback rules (H4, H1, M1)
│   └── risk.py            # Session management, Drawdowns
├── dashboard/             # React Frontend Client
│   ├── public/            # Static assets (PWA manifest, icons)
│   ├── src/               # React Code (components, hooks, pages)
│   └── android/           # Capacitor Native Android Studio project
├── data/                  # SQLite DB, Splits, and Historical CSVs
├── database/              # SQLite managers, Migrations, Seeders
├── indicators/            # Technical analysis indicators (RSI, MACD)
├── integrations/          # Telegram Bot & Gemini AI Client
├── rl/                    # Reinforcement learning pipeline
│   ├── agent.py           # Inference Agent (loads PPO models)
│   ├── evaluate.py        # Out-of-Sample evaluation script
│   ├── trading_env.py     # Gymnasium environment
│   └── train.py           # Stable-Baselines3 training script
├── scripts/               # DB Backups, historical data fetchers
├── main.py                # Main system coordinator
├── bot_engine.py          # Multi-tenant live trading engine
├── run_all.bat            # Standard launcher script
├── requirements.txt       # Python dependencies list
└── .env.example           # Example environment variables template
```

---

## 🚀 Installation & Quick Start

### 1. Prerequisites
*   Python **3.11.x**
*   NodeJS **18.x** or **20.x**
*   MetaTrader 5 Client Terminal installed on Windows.

### 2. Backend Installation
Clone the repository and run:
```bash
# Install python dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root folder with the following variables:
```ini
# MetaTrader 5 Configurations
MT5_LOGIN=5051162188
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo

# Telegram Bot API Configurations
TELEGRAM_TOKEN=your_telegram_bot_token
ALLOWED_CHAT_IDS=[123456789]

# Google Sign-In Configurations
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
VITE_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com

# System Configurations
JWT_SECRET=nur-jwt-secret-your-custom-string
GEMINI_API_KEY=your_gemini_api_key
```

### 4. Running the Dashboard Web UI
Install frontend dependencies and start Vite dev server:
```bash
cd dashboard
npm install
npm run dev
```
The interface will be served at `http://localhost:5173`.

### 5. Running the Bot & API Server
Run the quick-start batch script:
```bash
run_all.bat
```
This script automatically:
1. Launches MetaTrader 5.
2. Starts the Bot watchdog (`main.py` which boots the Bot engine and Telegram bot).
3. Launches the FastAPI server (Port `8000`).

---

## 🤖 3-Agent MARL Reinforcement Learning Pipeline

To train and evaluate the multi-agent reinforcement learning (MARL) framework, follow these steps:

### Step 1: Download Historical Data from MT5
Ensure MetaTrader 5 is running and logged in. Run:
```bash
python scripts/fetch_history.py
```
This downloads 3 years of M1 bars, splits the dataset, and saves them to:
*   `data/train_xauusd_m1.csv` (70% training split)
*   `data/val_xauusd_m1.csv` (15% validation split)
*   `data/test_xauusd_m1.csv` (15% testing split)

### Step 2: Train the MARL Framework (HMM + PPO Trend & Range)
Train the HMM classifier followed by the specialized reinforcement learning agents:
```bash
# Fits HMM on historical data and trains specialized Trend & Range PPO agents for 2,000,000 steps each
python -m rl.train --timesteps 2000000
```
This script automates:
1.  **HMM Fitting**: Fits transition and emission probabilities on training data and saves the parameters to `rl/models/hmm_model.json`.
2.  **Trend Agent Training**: Trains a PPO agent (`ppo_trend.zip`) in a custom environment filtered exclusively for HMM Trend states.
3.  **Range Agent Training**: Trains a PPO agent (`ppo_range.zip`) in a custom environment filtered exclusively for HMM Range states.
4.  **Fallback Agent Training**: Trains a PPO agent (`ppo_xauusd.zip`) on the full training dataset as a universal fallback agent.

### Step 3: Out-of-Sample Evaluation
Evaluate the trained agents on the out-of-sample test split:
```bash
python -m rl.evaluate
```
This executes backtests for individual agents and the combined **HMM-routed MARL Orchestrator** (`RLAgent`), calculates metrics (Sharpe ratio, drawdown, win rates), and plots the out-of-sample equity curve to `rl/results/equity_curve.png`.

---

## 🧠 Mathematical & RL Framework

The system partitions the problem of trading into a **Hierarchical Multi-Agent Reinforcement Learning (MARL)** architecture. Decoupling market regime detection from execution allows the models to optimize for specific market conditions instead of trying to learn a single compromise policy.

```mermaid
graph TD
    MarketData["Market Ticks (RSI, MACD, ATR)"] --> Agent1["Agent 1: HMM Router (Market Regime Classifier)"]
    Agent1 -->|State 0: RANGE| Agent3["Agent 3: Range PPO Agent (ppo_range)"]
    Agent1 -->|State 1: TREND| Agent2["Agent 2: Trend PPO Agent (ppo_trend)"]
    Agent1 -->|Fallback / HMM Error| Agent4["Agent 4: Fallback PPO Agent (ppo_xauusd)"]
    
    Agent3 -->|Action| TradeExec["Order Execution Loop (bot_engine.py)"]
    Agent2 -->|Action| TradeExec
    Agent4 -->|Action| TradeExec
```

---

### 1. Agent 1: HMM Classifier (Market Regime Router)
*   **Role**: Acts as the meta-controller. It dynamically partitions market structures and routes live execution commands to the PPO agent optimized for that specific state.
*   **Observation Vector ($X_t$)**: 3-dimensional momentum and volatility vector:
    $$\mathbf{x}_t = \left[ \Delta \log(\text{Close}_t), \text{ATR}_t^{\text{norm}}, \text{RSI}_t^{\text{norm}} \right]^T$$
*   **Decoded Regimes ($S_t$)**:
    *   $S_t = 0$: **RANGING (Range)** (Mean normalized ATR $\approx -0.54$) — Low-volatility, mean-reverting consolidation.
    *   $S_t = 1$: **TRENDING (Trend)** (Mean normalized ATR $\approx +0.86$) — High-volatility, directional breakouts.
*   **Decoding Engine**: Runs a rolling 100-candle Viterbi sequence decoder to find the optimal path of hidden states:
    $$\hat{s}_{1:T} = \arg\max_{s_{1:T}} P(s_{1:T} \mid x_{1:T})$$
    If the rolling window has fewer than 10 candles, it instantly falls back to a point PDF (Probability Density Function) density check:
    $$\hat{s}_t = \arg\max_{i \in \{0, 1\}} \mathcal{N}(\mathbf{x}_t \mid \boldsymbol{\mu}_i, \boldsymbol{\Sigma}_i)$$

---

### 2. Agent 2: Trend PPO Agent (`ppo_trend`)
*   **Role**: Specialized in trend-following, momentum riding, and breakout execution during high-volatility trending markets.
*   **Training Filter**: Trained on environment where `target_regime = 'trend'`. When the fitted HMM classifies a state as $S_t = 0$ (Range), the environment overrides all agent actions to `HOLD`. This isolates the model so it never learns or receives rewards from ranging consolidation, preventing "whipsaw" losses.
*   **Observation Space ($\mathbf{o}_t$)**: Normalized 7D state vector.
*   **Strategy & Behavior**:
    *   Optimized to ride long trends on M1 that align with macro H1/H4 timeframes.
    *   Rewarded for holding winning positions longer to capture large pip ranges.
    *   Highly penalized for opening counter-trend trades.

---

### 3. Agent 3: Range PPO Agent (`ppo_range`)
*   **Role**: Specialized in mean-reversion, pullback buys, and rally sells during low-volatility ranging markets.
*   **Training Filter**: Trained on environment where `target_regime = 'range'`. When the fitted HMM classifies a state as $S_t = 1$ (Trend), the environment overrides all agent actions to `HOLD`. This isolates the model so it never learns or receives rewards from breakout moves where mean reversion would fail.
*   **Observation Space ($\mathbf{o}_t$)**: Normalized 7D state vector.
*   **Strategy & Behavior**:
    *   Optimized to buy support levels (oversold RSI) and sell resistance levels (overbought RSI).
    *   Implements a time-decay holding penalty ($R_{\text{hold}} = -0.1$ per tick) to discourage long holds, forcing the model to take quick scalps.
    *   Highly penalized for trend-chasing behaviors.

---

### 4. Agent 4: Fallback PPO Agent (`ppo_xauusd`)
*   **Role**: Universal generalist that acts as a backup safety net.
*   **Training Filter**: Trained on the full 3-year historical dataset with no HMM filtering (`target_regime = None`).
*   **Strategy & Behavior**:
    *   Learns a generalized compromise policy across all market regimes.
    *   Used as a fallback when HMM confidence is low, when feature windows are cold-starting, or under system error conditions.

---

### 5. Common Parameters & General Reward Formulation
*   **Observation Vector Normalization**:
    *   $\text{RSI}^{\text{norm}} = \text{clip}((\text{RSI} - 50) / 50, -1.0, 1.0)$
    *   $\text{MACD\_hist}^{\text{norm}} = \tanh(\text{MACD\_hist})$
    *   $\text{EMA\_distance}^{\text{norm}} = \text{clip}((\text{Price} - \text{EMA}) / \text{EMA} \times 100, -1.0, 1.0)$
    *   $\text{ATR}^{\text{norm}} = \text{clip}((\text{ATR} - 1.5) / 1.0, -1.0, 1.0)$
    *   $\text{Hour}^{\text{norm}} = (\text{Hour} / 23 \times 2) - 1.0$
    *   $\text{Session}^{\text{norm}} = (\text{Session} / 3 \times 2) - 1.0$ (0: Asian, 1: London, 2: NY)
    *   $\text{Position}^{\text{norm}} = \{0: 0.0, 1: 1.0, 2: -1.0\}$ (Flat, Long, Short)
*   **Reward Function**:
    $$R_t = \Delta \text{Equity}_t - (\alpha \times \text{Drawdown}_t) - (\beta \times \text{Transaction Costs})$$
    Where $\alpha = 0.5$ penalizes floating drawdowns, and $\beta = 2.0$ represents invalid actions (e.g., trying to buy when already in a buy trade).

---

## 📱 Mobile Application compilation

### 1. Progressive Web App (PWA)
A PWA manifest and service worker are automatically configured.
*   Open the dashboard on your phone via Chrome or Safari (`http://<your-pc-ip>:5173`).
*   Select **Add to Home Screen** from the browser options to install the app.

### 2. Android APK Installation File
We use Capacitor to wrap the React application into a native Android app:
1.  Run `npm run build` in `dashboard` to compile the web files.
2.  Open **Android Studio**.
3.  Select **Open Project** and choose the folder:
    📁 `dashboard/android`
4.  Wait for Gradle to finish syncing.
5.  Go to the top menu and click:
    👉 **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
6.  Once built, click **Locate** to find the `app-debug.apk` file, transfer it to your phone, and install it!

---

## 🚨 Disclaimer
Educational / demo use only. Algorithmic trading involves significant financial risks. Past performance does not guarantee future results.
