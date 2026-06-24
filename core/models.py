from pydantic import BaseModel, Field

class Bar(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int

class Tick(BaseModel):
    time: int
    bid: float
    ask: float
    last: float
    volume: float

class RiskConfig(BaseModel):
    risk_percent: float = Field(default=1.0, ge=0.01, le=10.0)
    max_daily_loss: float = Field(default=500.0, gt=0.0)
    max_trades_per_day: int = Field(default=10, gt=0)
    max_drawdown_limit: float = Field(default=1000.0, gt=0.0)
    london_start: str = Field(default="08:00")
    london_end: str = Field(default="16:00")
    ny_start: str = Field(default="13:00")
    ny_end: str = Field(default="21:00")
    timezone_offset: str = Field(default="+00:00")

    # News filter settings
    news_filter_enabled: bool = Field(default=True, description="Enable/disable the hard news blackout gate")
    news_buffer_minutes: int = Field(default=30, ge=5, le=120)
    rl_veto_enabled: bool = Field(default=False, description="Enable/disable the RL agent confirmation filter")

    # Panic / circuit breaker thresholds
    panic_daily_loss_limit: float = Field(default=200.0, gt=0.0)
    panic_drawdown_limit: float = Field(default=100.0, gt=0.0)
    panic_margin_multiplier: float = Field(default=1.5, gt=1.0)
    panic_spread_threshold: float = Field(default=0.02, gt=0.0)

class StrategyConfig(BaseModel):
    symbol: str = "XAUUSD"
    ema_period: int = 200
    atr_period: int = 14
    atr_multiplier: float = 0.5
    trail_atr_multiplier: float = 1.2
    sl_atr_multiplier: float = 1.5
    deviation: int = 20
    cooldown_seconds: int = 30
    ema_min_buffer: float = 0.15

    # RL cost parameters
    spread_points: float = 2.0
    commission_per_lot: float = 0.5
    take_profit_method: str = "none"  # none, atr, rr
    take_profit_atr_multiplier: float = 1.5
    take_profit_rr: float = 1.5
