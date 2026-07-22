"""
core/cache_manager.py

Two-tier caching for the ISRO SOC Analytics platform:

  Tier 1 — Streamlit in-process cache (@st.cache_data)
            Fast, per-session, automatic TTL management.
            Used for ES aggregation results during a user session.

  Tier 2 — Joblib disk cache (Memory)
            Persistent across restarts, useful for expensive ML computations
            and pre-computed aggregation summaries.

Usage:
    from core import get_cache

    cache = get_cache()

    # Wrap any callable with Tier 2 caching:
    result = cache.disk_cache(expensive_function)(arg1, arg2)

    # Manual cache control:
    cache.clear_disk_cache()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import joblib

from config import settings, get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CacheManager:
    """
    Manages disk-based caching via joblib.Memory.

    Streamlit's @st.cache_data decorator is applied directly in page code
    (because it needs to wrap Streamlit-aware functions).
    This class handles the persistent disk-level cache for computations
    that are expensive and reproducible regardless of Streamlit session.
    """

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self._cache_dir = cache_dir or settings.joblib_cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory = joblib.Memory(location=str(self._cache_dir), verbose=0)
        logger.info("CacheManager initialised — disk cache at: %s", self._cache_dir)

    # ─── Disk cache ───────────────────────────────────────────────────────────

    def disk_cache(self, func: F) -> F:
        """
        Decorator — wraps a function with joblib disk-based caching.

        The cached result is stored based on the function's arguments.
        Re-use for expensive aggregation summaries, model training outputs, etc.

        Example:
            @cache.disk_cache
            def compute_baseline(index: str, from_dt: str, to_dt: str): ...
        """
        return self._memory.cache(func)  # type: ignore[return-value]

    def clear_disk_cache(self) -> None:
        """Clear all entries from the joblib disk cache."""
        self._memory.clear(warn=False)
        logger.info("Disk cache cleared.")

    def cache_size_mb(self) -> float:
        """
        Return approximate disk cache size in megabytes.
        Useful for displaying on the Settings page.
        """
        total_bytes = sum(
            f.stat().st_size
            for f in self._cache_dir.rglob("*")
            if f.is_file()
        )
        return round(total_bytes / (1024 * 1024), 2)

    # ─── Streamlit cache helpers ──────────────────────────────────────────────

    @staticmethod
    def get_streamlit_cache_ttl() -> int:
        """Return configured Streamlit cache TTL in seconds."""
        return settings.cache_ttl_seconds

    @staticmethod
    def build_cache_key(*parts: Any) -> str:
        """
        Build a deterministic string cache key from arbitrary parts.

        Used when constructing manual cache keys for st.session_state.

        Args:
            *parts: Any JSON-serialisable values.

        Returns:
            A string key like "part1|part2|part3".
        """
        return "|".join(str(p) for p in parts)

    # ─── Session state helpers ────────────────────────────────────────────────

    @staticmethod
    def get_from_session(key: str, default: Any = None) -> Any:
        """
        Retrieve a value from st.session_state safely.

        Falls back to ``default`` if key is missing or Streamlit is not running.
        """
        try:
            import streamlit as st
            return st.session_state.get(key, default)
        except Exception:
            return default

    @staticmethod
    def set_in_session(key: str, value: Any) -> None:
        """
        Store a value in st.session_state safely.
        No-op if Streamlit is not running (e.g., in unit tests).
        """
        try:
            import streamlit as st
            st.session_state[key] = value
        except Exception:
            pass

    @staticmethod
    def clear_session_key(key: str) -> None:
        """Remove a key from st.session_state."""
        try:
            import streamlit as st
            st.session_state.pop(key, None)
        except Exception:
            pass
