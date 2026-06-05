from datetime import datetime

def trading_session_open():
    hour = datetime.now().hour

    # London + NY sessions
    if 8 <= hour <= 22:
        return True

    return False