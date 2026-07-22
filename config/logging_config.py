"""
config/logging_config.py

Centralized logging configuration for the ISRO SOC Analytics platform.

Features:
  - Rotating file handler (10 MB max, 5 backups)
  - Console handler with colour-coded level labels
  - Per-module loggers via get_logger()
  - Log level driven by settings.log_level

Usage:
    from config import get_logger
    logger = get_logger(__name__)
    logger.info("Starting module...")
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


# ─── ANSI colour codes for console output ─────────────────────────────────────
_COLOURS = {
    "DEBUG":    "\033[36m",   # Cyan
    "INFO":     "\033[32m",   # Green
    "WARNING":  "\033[33m",   # Yellow
    "ERROR":    "\033[31m",   # Red
    "CRITICAL": "\033[35m",   # Magenta
}
_RESET = "\033[0m"


class _ColourFormatter(logging.Formatter):
    """Logging formatter that adds ANSI colour codes to level names."""

    _FMT = "[%(asctime)s] [{colour}%(levelname)-8s{reset}] [%(name)s] %(message)s"
    _DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOURS.get(record.levelname, "")
        fmt = self._FMT.format(colour=colour, reset=_RESET)
        formatter = logging.Formatter(fmt=fmt, datefmt=self._DATE_FMT)
        return formatter.format(record)


class _PlainFormatter(logging.Formatter):
    """Plain (no ANSI) formatter for file output."""

    _FMT = "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s"
    _DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATE_FMT)


_configured = False  # Guard against double-initialisation


def configure_logging(log_level: str = "INFO", logs_dir: Path | None = None) -> None:
    """
    Configure the root logger.  Safe to call multiple times (idempotent).

    Args:
        log_level: Logging level string ("DEBUG", "INFO", "WARNING", "ERROR").
        logs_dir:  Directory where rotating log files are written.
                   Defaults to <project_root>/logs/.
    """
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # ── Root logger ──────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid duplicate handlers if Streamlit re-runs configure_logging
    if root.handlers:
        root.handlers.clear()

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(_ColourFormatter())
    root.addHandler(console_handler)

    # ── Rotating file handler ────────────────────────────────────────────────
    if logs_dir is not None:
        logs_dir = Path(logs_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "isro_soc.log"

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(_PlainFormatter())
        root.addHandler(file_handler)

    # ── Silence noisy third-party libraries ──────────────────────────────────
    for noisy_lib in ("elastic_transport", "urllib3", "matplotlib"):
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

    _configured = True

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging initialised — level=%s, log_file=%s",
        log_level,
        (logs_dir / "isro_soc.log") if logs_dir else "console only",
    )


def get_logger(name: str) -> logging.Logger:
    """
    Factory function — returns a named logger.

    The root logger must have been configured via configure_logging() first;
    if not yet configured, this function will configure it with defaults.

    Args:
        name: Typically __name__ of the calling module.

    Returns:
        logging.Logger instance.
    """
    if not _configured:
        # Lazy-init with sensible defaults (useful in tests / standalone scripts)
        configure_logging(log_level="INFO")
    return logging.getLogger(name)
