"""
RL Inference Agent for XAUUSD Trading.

Wraps a trained PPO model to provide ``predict`` (action string) and
``get_confidence`` (action probability distribution) methods that can be
called by the live trading pipeline.

Usage:
    from rl.agent import RLAgent
    agent = RLAgent()
    action = agent.predict(state_dict)
    probs  = agent.get_confidence(state_dict)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
from stable_baselines3 import PPO

from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MODEL_PATH: Path = Path(__file__).resolve().parent / "models" / "ppo_xauusd.zip"

_ACTION_MAP: dict[int, str] = {0: "HOLD", 1: "BUY", 2: "SELL"}

_POSITION_MAP: dict[int, float] = {
    0: 0.0,   # flat
    1: 1.0,   # long
    2: -1.0,  # short
}


class RLAgent:
    """Inference wrapper around the trained PPO trading model.

    Parameters:
        model_path: Path to the saved ``.zip`` model file.  Falls back to
            the default ``rl/models/ppo_xauusd.zip`` when *None*.
    """

    def __init__(self, model_path: Path | str | None = None) -> None:
        resolved: Path = Path(model_path) if model_path else _MODEL_PATH
        self._model: PPO | None = None
        self.has_manual_override = False

        if resolved.is_file():
            self._model = PPO.load(str(resolved))
            logger.info("PPO model loaded from %s", resolved)
        else:
            logger.warning(
                "Model file not found at %s – agent will default to HOLD.",
                resolved,
            )

    # ------------------------------------------------------------------
    # Observation builder
    # ------------------------------------------------------------------
    @staticmethod
    def _build_observation(state: dict[str, Any]) -> np.ndarray:
        """Convert a raw state dictionary into a normalised numpy vector.

        Normalization scheme (must match ``XAUUSDTradingEnv``):
            * rsi           → (rsi − 50) / 50, clipped to [-1, 1]
            * macd_hist     → tanh(macd_hist)   (pre-normalised by caller)
            * ema_distance_pct → clipped to [-1, 1]   (pre-normalised)
            * atr_normalized   → clipped to [-1, 1]   (pre-normalised)
            * hour          → hour / 23 × 2 − 1
            * session       → session / 3 × 2 − 1
            * position      → {0: 0.0, 1: 1.0, 2: −1.0}
        """
        rsi: float = state.get("rsi", 50.0)
        macd_hist: float = state.get("macd_hist", 0.0)
        ema_dist: float = state.get("ema_distance_pct", 0.0)
        atr_norm: float = state.get("atr_normalized", 0.0)
        hour: float = state.get("hour", 12.0)
        session: float = state.get("session", 0.0)
        position: int = state.get("position", 0)

        rsi_norm: float = float(np.clip((rsi - 50.0) / 50.0, -1.0, 1.0))
        macd_norm: float = float(np.tanh(macd_hist))
        ema_norm: float = float(np.clip(ema_dist, -1.0, 1.0))
        atr_n: float = float(np.clip(atr_norm, -1.0, 1.0))
        hour_norm: float = hour / 23.0 * 2.0 - 1.0
        session_norm: float = session / 3.0 * 2.0 - 1.0
        pos_norm: float = _POSITION_MAP.get(position, 0.0)

        obs = np.array(
            [rsi_norm, macd_norm, ema_norm, atr_n, hour_norm, session_norm, pos_norm],
            dtype=np.float32,
        )
        return obs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def predict(self, state_dict: dict[str, Any]) -> str:
        """Return the deterministic trading action for the given state.

        Args:
            state_dict: Dictionary with keys ``rsi``, ``macd_hist``,
                ``ema_distance_pct``, ``atr_normalized``, ``hour``,
                ``session``, ``position``.

        Returns:
            One of ``'HOLD'``, ``'BUY'``, ``'SELL'``.
        """
        if self.has_manual_override:
            state_dict["is_manual_active"] = 1
            return "HOLD"

        if self._model is None:
            return "HOLD"

        obs = self._build_observation(state_dict)
        action, _ = self._model.predict(obs, deterministic=True)
        return _ACTION_MAP.get(int(action), "HOLD")

    def get_confidence(self, state_dict: dict[str, Any]) -> dict[str, float]:
        """Return the action probability distribution for the given state.

        Args:
            state_dict: Same format as for :meth:`predict`.

        Returns:
            Dictionary mapping ``'HOLD'``, ``'BUY'``, ``'SELL'`` to their
            respective probabilities (summing to ≈ 1.0).
        """
        if self.has_manual_override:
            state_dict["is_manual_active"] = 1
            return {"HOLD": 1.0, "BUY": 0.0, "SELL": 0.0}

        if self._model is None:
            return {"HOLD": 1.0, "BUY": 0.0, "SELL": 0.0}

        try:
            obs = self._build_observation(state_dict)
            obs_tensor = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            obs_tensor = obs_tensor.to(self._model.policy.device)

            distribution = self._model.policy.get_distribution(obs_tensor)
            probs = distribution.distribution.probs.detach().cpu().numpy().flatten()

            return {
                "HOLD": float(probs[0]),
                "BUY": float(probs[1]),
                "SELL": float(probs[2]),
            }
        except Exception:
            logger.exception("Failed to compute action probabilities – returning uniform.")
            return {"HOLD": 0.333, "BUY": 0.333, "SELL": 0.333}

    def sync_with_manual_positions(self, manual_positions_list: list) -> dict:
        """
        When user manually trades, agent reads it and adapts.
        
        Parameters:
        - manual_positions_list: List of open positions with magic != NUR_MAGIC
        
        Behavior:
        If manual trades exist:
            1. Set internal flag: self.has_manual_override = True
            2. Read manual position direction (BUY/SELL)
            3. Inject into state vector as: "is_manual_active" = 1
            4. Change strategy from "SEEKING_ENTRY" to "MANUAL_TRAILING"
            5. Start monitoring for stop-loss breach or TP hit
            6. Block new entries until manual trade closes
        
        Return: {"mode": "MANUAL_TRAILING", "monitoring": True}
        """
        if manual_positions_list:
            self.has_manual_override = True
            return {"mode": "MANUAL_TRAILING", "monitoring": True}
        else:
            self.has_manual_override = False
            return {"mode": "SEEKING_ENTRY", "monitoring": False}
