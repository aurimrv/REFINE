import logging
import os
from datetime import datetime
import colorlog

def setup_logger(name: str) -> logging.Logger:
    """
    Configure and return a logger with colored console output and file logging.
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.hasHandlers():
        return logger
        
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # File handler
    log_filename = f"logs/openapi_improver_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    color_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(color_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
