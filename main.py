#!/usr/bin/env python3
import sys
import threading
import time
import shared_state

print("PYTHON EXECUTABLE:", sys.executable)
print("PYTHON VERSION:", sys.version)

import bot_engine
from integrations.telegram_bot import run_telegram

def run_trading_engine():
    try:
        bot_engine.main()
    except Exception as e:
        print(f"❌ Trading Engine crashed on startup: {e}")

if __name__ == "__main__":

    # 🔥 Start Telegram first
    t2 = threading.Thread(target=run_telegram, daemon=True)
    t2.start()

    time.sleep(2)

    # 🔥 Start Bot
    t1 = threading.Thread(target=run_trading_engine, daemon=True)
    t1.start()

    try:
        # 👇 Keep main thread alive (but interruptible)
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 SHUTTING DOWN...")

        shared_state.shutdown = True
        shared_state.bot_running = False

        time.sleep(2)

        print("✅ EXITED CLEANLY")
        # python main
