"""
config/__init__.py

Exposes the singleton Settings instance and the configured logger
so any module can do:

    from config import settings, get_logger
    logger = get_logger(__name__)
"""

from config.settings import settings
from config.logging_config import get_logger

__all__ = ["settings", "get_logger"]
