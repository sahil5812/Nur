import logging
import os

# Ensure logs dir exists
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("NUR_Bot")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

# File handler
file_handler = logging.FileHandler("logs/trading.log", encoding="utf-8")
file_handler.setFormatter(formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Prevent duplicate handlers
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def get_logger(name: str):
    """
    Returns a configured logger instance for the given name.
    Ensures backward compatibility with database and API modules.
    """
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    if not log.handlers:
        log.addHandler(file_handler)
        log.addHandler(console_handler)
    return log
