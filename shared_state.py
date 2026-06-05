import threading
import sys

class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self._bot_running = True
        self._shutdown = False
        self._chat_id = None
        self._send_message = None
        self._panic_mode = False
        self._soft_stop = False
        self._hard_stop = False
        self._authenticated = False

    @property
    def authenticated(self) -> bool:
        with self._lock:
            return self._authenticated

    @authenticated.setter
    def authenticated(self, val: bool):
        with self._lock:
            self._authenticated = val

    @property
    def bot_running(self) -> bool:
        with self._lock:
            return self._bot_running

    @bot_running.setter
    def bot_running(self, val: bool):
        with self._lock:
            self._bot_running = val

    @property
    def shutdown(self) -> bool:
        with self._lock:
            return self._shutdown

    @shutdown.setter
    def shutdown(self, val: bool):
        with self._lock:
            self._shutdown = val

    @property
    def chat_id(self):
        with self._lock:
            return self._chat_id

    @chat_id.setter
    def chat_id(self, val):
        with self._lock:
            self._chat_id = val

    @property
    def send_message(self):
        with self._lock:
            return self._send_message

    @send_message.setter
    def send_message(self, val):
        with self._lock:
            self._send_message = val

    @property
    def panic_mode(self) -> bool:
        with self._lock:
            return self._panic_mode

    @panic_mode.setter
    def panic_mode(self, val: bool):
        with self._lock:
            self._panic_mode = val

    @property
    def soft_stop(self) -> bool:
        with self._lock:
            return self._soft_stop

    @soft_stop.setter
    def soft_stop(self, val: bool):
        with self._lock:
            self._soft_stop = val

    @property
    def hard_stop(self) -> bool:
        with self._lock:
            return self._hard_stop

    @hard_stop.setter
    def hard_stop(self, val: bool):
        with self._lock:
            self._hard_stop = val

# Replace the module with the class instance to allow thread-safe property access
sys.modules[__name__] = SharedState()