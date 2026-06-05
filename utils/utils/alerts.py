import shared_state

def notify(message):
    print(f"📢 {message}")  # terminal

    if shared_state.send_message:
        try:
            shared_state.send_message(message)
        except Exception as e:
            print(f"❌ Telegram Error: {e}")