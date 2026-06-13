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
    """Inference router wrapper around the trained PPO MARL trading models.

    Parameters:
        model_dir: Path to the models directory. Falls back to
            the default ``rl/models/`` when *None*.
    """

    def __init__(self, model_dir: Path | str | None = None) -> None:
        resolved_dir = Path(model_dir) if model_dir else Path(__file__).resolve().parent / "models"
        self._hmm = None
        self._ppo_trend = None
        self._ppo_range = None
        self._ppo_fallback = None
        self.has_manual_override = False
        self._hmm_features = []
        self._last_candle_time = None

        # Load HMM model
        hmm_path = resolved_dir / "hmm_model.json"
        if hmm_path.is_file():
            try:
                from rl.hmm_classifier import GaussianHMM
                self._hmm = GaussianHMM()
                self._hmm.load(hmm_path)
                logger.info("MARL HMM model loaded from %s", hmm_path)
            except Exception as e:
                logger.error("Failed to load HMM model: %s", e)

        # Load Trend PPO
        trend_path = resolved_dir / "ppo_trend.zip"
        if trend_path.is_file():
            try:
                self._ppo_trend = PPO.load(str(trend_path))
                logger.info("MARL Trend PPO model loaded from %s", trend_path)
            except Exception as e:
                logger.error("Failed to load Trend PPO: %s", e)
            
        # Load Range PPO
        range_path = resolved_dir / "ppo_range.zip"
        if range_path.is_file():
            try:
                self._ppo_range = PPO.load(str(range_path))
                logger.info("MARL Range PPO model loaded from %s", range_path)
            except Exception as e:
                logger.error("Failed to load Range PPO: %s", e)

        # Load Fallback/Universal PPO
        fallback_path = resolved_dir / "ppo_xauusd.zip"
        if fallback_path.is_file():
            try:
                self._ppo_fallback = PPO.load(str(fallback_path))
                logger.info("MARL Fallback PPO model loaded from %s", fallback_path)
            except Exception as e:
                logger.error("Failed to load Fallback PPO: %s", e)

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

    def _get_hmm_state_with_confidence(self, state_dict: dict[str, Any]) -> tuple[int, float]:
        """Decodes the current regime state (0 for RANGE, 1 for TREND) and returns confidence score [0.0, 1.0]."""
        if self._hmm is None:
            return 0, 1.0
            
        log_ret = state_dict.get("log_ret", 0.0)
        atr_n = np.clip(state_dict.get("atr_normalized", 0.0), -3.0, 3.0)
        rsi = state_dict.get("rsi", 50.0)
        rsi_n = np.clip((rsi - 50.0) / 50.0, -1.0, 1.0)
        
        feat = np.array([log_ret, atr_n, rsi_n], dtype=np.float32)
        
        # Deduplication based on candle time
        candle_time = state_dict.get("candle_time")
        should_append = False
        if candle_time is not None:
            if candle_time != self._last_candle_time:
                self._last_candle_time = candle_time
                should_append = True
        else:
            # If no candle time, check if feature has changed or buffer is empty
            if not self._hmm_features or not np.allclose(self._hmm_features[-1], feat):
                should_append = True
                
        if should_append:
            self._hmm_features.append(feat)
            if len(self._hmm_features) > 100:
                self._hmm_features.pop(0)
                
        # Sequence decoding vs point PDF fallback
        if len(self._hmm_features) >= 10:
            try:
                X = np.array(self._hmm_features)
                states = self._hmm.predict(X)
                state = int(states[-1])
                
                # Sequence-level posterior confidence check using Forward-Backward algorithm
                B = self._hmm._get_emissions(X)
                alpha, c = self._hmm._forward(B)
                beta = self._hmm._backward(B, c)
                gamma = alpha * beta
                gamma = gamma / (np.sum(gamma, axis=1, keepdims=True) + 1e-12)
                
                confidence = float(gamma[-1, state])
                return state, confidence
            except Exception as e:
                logger.warning("HMM sequence decode failed, falling back to PDF: %s", e)
                
        # PDF fallback
        try:
            p0 = self._hmm._pdf(feat, 0)
            p1 = self._hmm._pdf(feat, 1)
            total = p0 + p1 + 1e-12
            state = 0 if p0 > p1 else 1
            confidence = p0 / total if state == 0 else p1 / total
            return state, float(confidence)
        except Exception as e:
            logger.warning("HMM PDF computation failed: %s", e)
            return 0, 1.0

    def _get_hmm_state(self, state_dict: dict[str, Any]) -> int:
        """Helper to get HMM state (for backward compatibility)."""
        state, _ = self._get_hmm_state_with_confidence(state_dict)
        return state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def predict(self, state_dict: dict[str, Any]) -> str:
        """Return the deterministic trading action for the given state.

        Args:
            state_dict: Dictionary with keys ``rsi``, ``macd_hist``,
                ``ema_distance_pct``, ``atr_normalized``, ``hour``,
                ``session``, ``position``, and ``log_ret``.

        Returns:
            One of ``'HOLD'``, ``'BUY'``, ``'SELL'``.
        """
        if self.has_manual_override:
            state_dict["is_manual_active"] = 1
            return "HOLD"

        # 1. Determine active model using HMM routing with confidence check
        model = self._ppo_fallback
        confidence_threshold = 0.75  # Must be at least 75% sure of regime to switch
        
        if self._hmm is not None:
            try:
                hmm_state, hmm_conf = self._get_hmm_state_with_confidence(state_dict)
                # Expose regime routing results in state_dict for audit trail
                state_dict["hmm_state"] = hmm_state
                state_dict["hmm_confidence"] = hmm_conf
                
                if hmm_conf >= confidence_threshold:
                    if hmm_state == 1 and self._ppo_trend is not None:
                        model = self._ppo_trend
                    elif hmm_state == 0 and self._ppo_range is not None:
                        model = self._ppo_range
                else:
                    logger.info(f"Regime transition / low confidence ({hmm_conf:.2f} < {confidence_threshold:.2f}) — routing to universal PPO")
                    model = self._ppo_fallback
            except Exception as e:
                logger.warning("HMM prediction failed: %s — using fallback", e)

        if model is None:
            model = self._ppo_trend or self._ppo_range or self._ppo_fallback

        if model is None:
            return "HOLD"

        obs = self._build_observation(state_dict)
        action, _ = model.predict(obs, deterministic=True)
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

        model = self._ppo_fallback
        confidence_threshold = 0.75
        
        if self._hmm is not None:
            try:
                hmm_state, hmm_conf = self._get_hmm_state_with_confidence(state_dict)
                if hmm_conf >= confidence_threshold:
                    if hmm_state == 1 and self._ppo_trend is not None:
                        model = self._ppo_trend
                    elif hmm_state == 0 and self._ppo_range is not None:
                        model = self._ppo_range
                else:
                    model = self._ppo_fallback
            except Exception:
                pass

        if model is None:
            model = self._ppo_trend or self._ppo_range or self._ppo_fallback

        if model is None:
            return {"HOLD": 1.0, "BUY": 0.0, "SELL": 0.0}

        try:
            obs = self._build_observation(state_dict)
            obs_tensor = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
            obs_tensor = obs_tensor.to(model.policy.device)

            distribution = model.policy.get_distribution(obs_tensor)
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
        """When user manually trades, agent reads it and adapts."""
        if manual_positions_list:
            self.has_manual_override = True
            return {"mode": "MANUAL_TRAILING", "monitoring": True}
        else:
            self.has_manual_override = False
            return {"mode": "SEEKING_ENTRY", "monitoring": False}
