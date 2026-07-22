"""
utils/time_utils.py

Timezone-aware time utilities for the ISRO SOC Analytics platform.

All time handling uses UTC internally. Conversion to local time zones
happens only at the display layer.

Usage:
    from utils import TimeUtils

    start, end = TimeUtils.last_n_days(7)
    buckets = TimeUtils.auto_interval(start, end)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Tuple

import pytz

from config import get_logger

logger = get_logger(__name__)

# Default time zone for display (can be overridden in Settings page)
DEFAULT_DISPLAY_TZ = "UTC"


class TimeUtils:
    """Static utility methods for time range handling."""

    # ─── UTC helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def now_utc() -> datetime:
        """Return current UTC datetime (timezone-aware)."""
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """Convert any timezone-aware datetime to UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def to_iso8601(dt: datetime) -> str:
        """Return ISO-8601 string in UTC (with 'Z' suffix)."""
        utc_dt = TimeUtils.to_utc(dt)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def from_iso8601(s: str) -> datetime:
        """Parse an ISO-8601 string into a UTC-aware datetime."""
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(s, fmt)
                return TimeUtils.to_utc(dt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime string: {s!r}")

    # ─── Preset time ranges ───────────────────────────────────────────────────

    @staticmethod
    def last_n_hours(n: int) -> Tuple[str, str]:
        """Return (from_iso, to_iso) for the last N hours."""
        now = TimeUtils.now_utc()
        start = now - timedelta(hours=n)
        return TimeUtils.to_iso8601(start), TimeUtils.to_iso8601(now)

    @staticmethod
    def last_n_days(n: int) -> Tuple[str, str]:
        """Return (from_iso, to_iso) for the last N days."""
        now = TimeUtils.now_utc()
        start = now - timedelta(days=n)
        return TimeUtils.to_iso8601(start), TimeUtils.to_iso8601(now)

    @staticmethod
    def last_n_minutes(n: int) -> Tuple[str, str]:
        """Return (from_iso, to_iso) for the last N minutes."""
        now = TimeUtils.now_utc()
        start = now - timedelta(minutes=n)
        return TimeUtils.to_iso8601(start), TimeUtils.to_iso8601(now)

    @staticmethod
    def full_day_utc(date: datetime) -> Tuple[str, str]:
        """Return start and end of a full UTC day for the given date."""
        start = datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=timezone.utc)
        return TimeUtils.to_iso8601(start), TimeUtils.to_iso8601(end)

    @staticmethod
    def june_2026_range() -> Tuple[str, str]:
        """Return the full date range covering the June 2026 dataset."""
        start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
        return TimeUtils.to_iso8601(start), TimeUtils.to_iso8601(end)

    # ─── Smart interval selection ─────────────────────────────────────────────

    @staticmethod
    def auto_interval(from_iso: str, to_iso: str) -> str:
        """
        Automatically select a sensible date_histogram calendar_interval
        based on the time range duration.

        Returns an ES calendar_interval string like "1h", "1d", "1w".
        """
        try:
            start = TimeUtils.from_iso8601(from_iso)
            end = TimeUtils.from_iso8601(to_iso)
        except ValueError:
            return "1h"

        delta = end - start
        hours = delta.total_seconds() / 3600

        if hours <= 2:
            return "1m"
        elif hours <= 24:
            return "1h"
        elif hours <= 7 * 24:
            return "6h"
        elif hours <= 30 * 24:
            return "1d"
        elif hours <= 90 * 24:
            return "1w"
        else:
            return "1M"

    @staticmethod
    def duration_label(from_iso: str, to_iso: str) -> str:
        """
        Return a human-readable label for a time range duration.
        e.g. "Last 24 hours", "30 days", "2 hours".
        """
        try:
            start = TimeUtils.from_iso8601(from_iso)
            end = TimeUtils.from_iso8601(to_iso)
        except ValueError:
            return "Custom range"

        delta = end - start
        total_seconds = int(delta.total_seconds())

        if total_seconds < 3600:
            return f"{total_seconds // 60} minutes"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600} hours"
        elif total_seconds < 86400 * 7:
            return f"{total_seconds // 86400} days"
        elif total_seconds < 86400 * 30:
            weeks = total_seconds // (86400 * 7)
            return f"{weeks} week{'s' if weeks > 1 else ''}"
        else:
            days = total_seconds // 86400
            return f"{days} days"

    # ─── Streamlit widget helpers ─────────────────────────────────────────────

    @staticmethod
    def streamlit_date_range_to_iso(
        start_date: "date",  # type: ignore[name-defined]  # noqa: F821
        end_date: "date",  # type: ignore[name-defined]  # noqa: F821
    ) -> Tuple[str, str]:
        """
        Convert Streamlit date_input values to ISO-8601 strings.

        Args:
            start_date: datetime.date from st.date_input
            end_date:   datetime.date from st.date_input

        Returns:
            Tuple of (from_iso, to_iso) strings.
        """
        from_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
        to_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)
        return TimeUtils.to_iso8601(from_dt), TimeUtils.to_iso8601(to_dt)

    @staticmethod
    def available_presets() -> dict:
        """
        Return preset time range options for Streamlit selectbox.

        Returns:
            Dict mapping label → (from_iso, to_iso) callables.
        """
        return {
            "Last 15 minutes": lambda: TimeUtils.last_n_minutes(15),
            "Last 1 hour": lambda: TimeUtils.last_n_hours(1),
            "Last 6 hours": lambda: TimeUtils.last_n_hours(6),
            "Last 24 hours": lambda: TimeUtils.last_n_hours(24),
            "Last 7 days": lambda: TimeUtils.last_n_days(7),
            "Last 30 days": lambda: TimeUtils.last_n_days(30),
            "All of June 2026": lambda: TimeUtils.june_2026_range(),
        }

    @staticmethod
    def parse_any(val: Any) -> datetime:
        """Parse datetime, date, or ISO string into a UTC-aware datetime."""
        if isinstance(val, datetime):
            return TimeUtils.to_utc(val)
        if isinstance(val, date) and not isinstance(val, datetime):
            return datetime(val.year, val.month, val.day, 0, 0, 0, tzinfo=timezone.utc)
        if isinstance(val, str):
            val_str = val.strip()
            for fmt in (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(val_str, fmt)
                    return TimeUtils.to_utc(dt)
                except ValueError:
                    continue
        raise ValueError(f"Cannot parse datetime from: {val!r}")

    @staticmethod
    def to_iso(val: Any) -> str:
        """Convert a datetime/date/string into an ISO-8601 UTC string ending in 'Z'."""
        if not val:
            return ""
        if isinstance(val, str):
            if val.startswith("now"):
                return val
            try:
                dt = TimeUtils.parse_any(val)
                return TimeUtils.to_iso8601(dt)
            except ValueError:
                return val
        try:
            dt = TimeUtils.parse_any(val)
            return TimeUtils.to_iso8601(dt)
        except Exception:
            return str(val)

    @staticmethod
    def list_presets() -> list[str]:
        """Return list of preset time range names."""
        return list(TimeUtils.available_presets().keys())

    @staticmethod
    def get_preset_range(preset_name: str) -> Tuple[datetime, datetime]:
        """
        Return (from_dt, to_dt) as UTC-aware datetime objects for the specified preset.
        """
        presets = TimeUtils.available_presets()
        if preset_name in presets:
            from_iso, to_iso = presets[preset_name]()
            return TimeUtils.from_iso8601(from_iso), TimeUtils.from_iso8601(to_iso)
        from_iso, to_iso = TimeUtils.last_n_hours(24)
        return TimeUtils.from_iso8601(from_iso), TimeUtils.from_iso8601(to_iso)

