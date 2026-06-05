import time
from utils.logger import logger

class StateMachine:
    STATE_WAITING = "WAITING"
    STATE_IN_TRADE = "IN_TRADE"
    STATE_COOLDOWN = "COOLDOWN"

    def __init__(self, cooldown_seconds: int = 30):
        self._state = self.STATE_WAITING
        self.cooldown_seconds = cooldown_seconds
        self.last_trade_time = None

    @property
    def current_state(self) -> str:
        return self._state

    def set_in_trade(self):
        if self._state != self.STATE_IN_TRADE:
            logger.info(f"🔄 State Transition: {self._state} ➔ {self.STATE_IN_TRADE}")
            self._state = self.STATE_IN_TRADE

    def set_cooldown(self):
        if self._state != self.STATE_COOLDOWN:
            logger.info(f"🔄 State Transition: {self._state} ➔ {self.STATE_COOLDOWN}")
            self._state = self.STATE_COOLDOWN
            self.last_trade_time = time.time()

    def set_waiting(self):
        if self._state != self.STATE_WAITING:
            logger.info(f"🔄 State Transition: {self._state} ➔ {self.STATE_WAITING}")
            self._state = self.STATE_WAITING

    def check_cooldown(self) -> bool:
        """
        Returns True if not in cooldown or if cooldown has finished (which resets state to WAITING).
        Returns False if still cooling down.
        """
        if self._state != self.STATE_COOLDOWN:
            return True
        
        if self.last_trade_time is None:
            self.set_waiting()
            return True
            
        elapsed = time.time() - self.last_trade_time
        if elapsed >= self.cooldown_seconds:
            self.set_waiting()
            return True
            
        return False
