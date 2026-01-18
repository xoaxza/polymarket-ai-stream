import logging
import sys
from datetime import datetime
from typing import Optional


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """Configure logging for the application"""
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Optionally add file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)


# Emoji-based status logging helpers
class StatusLogger:
    """Helper for logging with status emojis"""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def success(self, message: str) -> None:
        self.logger.info(f"✅ {message}")
    
    def error(self, message: str) -> None:
        self.logger.error(f"❌ {message}")
    
    def warning(self, message: str) -> None:
        self.logger.warning(f"⚠️ {message}")
    
    def info(self, message: str) -> None:
        self.logger.info(f"ℹ️ {message}")
    
    def start(self, message: str) -> None:
        self.logger.info(f"🚀 {message}")
    
    def stop(self, message: str) -> None:
        self.logger.info(f"⏹️ {message}")
    
    def vote(self, message: str) -> None:
        self.logger.info(f"🗳️ {message}")
    
    def trophy(self, message: str) -> None:
        self.logger.info(f"🏆 {message}")
    
    def mic(self, message: str) -> None:
        self.logger.info(f"🎙️ {message}")
    
    def wave(self, message: str) -> None:
        self.logger.info(f"👋 {message}")
