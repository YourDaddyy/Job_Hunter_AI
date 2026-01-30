"""Logging configuration for the job_hunter application.

This module provides a simple but effective logging setup with:
- File logging with rotation (10MB max, 5 backups)
- Optional console logging
- Structured log format with timestamps
- Component-specific loggers under the 'job_hunter' namespace
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logging(
    log_dir: str = "logs",
    log_file: str = "job_hunter.log",
    level: int = logging.INFO,
    console: bool = True
) -> None:
    """Configure logging for the application.

    Args:
        log_dir: Directory to store log files (default: "logs")
        log_file: Name of the log file (default: "job_hunter.log")
        level: Logging level (default: logging.INFO)
        console: Whether to also log to console (default: True)

    Example:
        >>> setup_logging()  # Use defaults
        >>> setup_logging(level=logging.DEBUG, console=False)  # Debug file only
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Set up formatters
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "%(levelname)s - %(name)s - %(message)s"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # File handler with rotation (10MB, 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler (optional)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Log startup message
    logger = get_logger("core")
    logger.info("Logging initialized (level=%s, file=%s, console=%s)",
                logging.getLevelName(level), log_path / log_file, console)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific component.

    All loggers are created under the 'job_hunter' namespace for easier
    filtering and management.

    Args:
        name: Name of the component (e.g., "database", "scraper", "filter")

    Returns:
        A configured logger instance

    Example:
        >>> logger = get_logger("scraper.linkedin")
        >>> logger.info("Starting LinkedIn scrape...")
        >>> logger.error("Failed to login", exc_info=True)
    """
    return logging.getLogger(f"job_hunter.{name}")
