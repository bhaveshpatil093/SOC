"""
config/settings.py

Centralized configuration management for the ISRO SOC Analytics
Platform. Loads values from environment variables (via .env file) and
provides a single typed Settings dataclass accessible across the app.

Usage:
    from config import settings
    print(settings.es_host)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# ─── Load .env ───────────────────────────────────────────────────────────────
# Resolve project root (one level above this file)
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_ENV_FILE = _PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=_ENV_FILE, override=False)


def _get(key: str, default: str = "") -> str:
    """Return env var value stripped of whitespace."""
    return os.getenv(key, default).strip()


def _get_int(key: str, default: int = 0) -> int:
    try:
        return int(_get(key, str(default)))
    except ValueError:
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    return _get(key, str(default)).lower() in {"true", "1", "yes"}


def _get_list(key: str, default: str = "", delimiter: str = ",") -> List[str]:
    raw = _get(key, default)
    return [item.strip() for item in raw.split(delimiter) if item.strip()]


# ─── Settings Dataclass ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Settings:
    """
    Immutable settings object — all configuration is read once at startup.
    To override any value, set the corresponding environment variable
    (or update .env) and restart the app.
    """

    # ── Application ─────────────────────────────────────────────────────────
    app_title: str = field(default_factory=lambda: _get("APP_TITLE", "ISRO SOC Analytics"))
    app_env: str = field(default_factory=lambda: _get("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: _get("LOG_LEVEL", "INFO").upper())
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)

    # ── Elasticsearch Connection ─────────────────────────────────────────────
    es_host: str = field(default_factory=lambda: _get("ES_HOST", "localhost"))
    es_port: int = field(default_factory=lambda: _get_int("ES_PORT", 9200))
    es_scheme: str = field(default_factory=lambda: _get("ES_SCHEME", "https"))
    es_username: str = field(default_factory=lambda: _get("ES_USERNAME", ""))
    es_password: str = field(default_factory=lambda: _get("ES_PASSWORD", ""))
    es_ca_cert: str = field(default_factory=lambda: _get("ES_CA_CERT", ""))
    es_max_concurrent_searches: int = field(
        default_factory=lambda: _get_int("ES_MAX_CONCURRENT_SEARCHES", 5)
    )

    # ── Index Configuration ──────────────────────────────────────────────────
    es_index_pattern: str = field(
        default_factory=lambda: _get("ES_INDEX_PATTERN", "security-logs-2026.06.*")
    )

    # ── Batch Processing ─────────────────────────────────────────────────────
    batch_size: int = field(default_factory=lambda: _get_int("BATCH_SIZE", 1000))
    scroll_keepalive: str = field(default_factory=lambda: _get("SCROLL_KEEPALIVE", "2m"))

    # ── Cache ────────────────────────────────────────────────────────────────
    cache_ttl_seconds: int = field(
        default_factory=lambda: _get_int("CACHE_TTL_SECONDS", 300)
    )
    joblib_cache_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / _get("JOBLIB_CACHE_DIR", "joblib_cache").lstrip("./")
    )

    # ── ML ───────────────────────────────────────────────────────────────────
    model_save_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / _get("MODEL_SAVE_DIR", "models/saved").lstrip("./")
    )

    # ── Log Retrieval — ECS Field Name Defaults ──────────────────────────────
    # These are Elastic Common Schema (ECS) defaults; override in .env if your
    # index uses different field names.
    es_time_field: str       = field(default_factory=lambda: _get("ES_TIME_FIELD",     "@timestamp"))
    es_hostname_field: str   = field(default_factory=lambda: _get("ES_HOSTNAME_FIELD", "host.name"))
    es_username_field: str   = field(default_factory=lambda: _get("ES_USERNAME_FIELD", "user.name"))
    es_src_ip_field: str     = field(default_factory=lambda: _get("ES_SRC_IP_FIELD",   "source.ip"))
    es_dst_ip_field: str     = field(default_factory=lambda: _get("ES_DST_IP_FIELD",   "destination.ip"))
    es_event_id_field: str   = field(default_factory=lambda: _get("ES_EVENT_ID_FIELD", "event.id"))
    es_severity_field: str   = field(default_factory=lambda: _get("ES_SEVERITY_FIELD", "event.severity"))
    es_category_field: str   = field(default_factory=lambda: _get("ES_CATEGORY_FIELD", "event.category"))

    # ── Log Retrieval — Safety Limits ────────────────────────────────────────
    retrieval_page_size: int  = field(default_factory=lambda: _get_int("RETRIEVAL_PAGE_SIZE",  100))
    retrieval_max_docs: int   = field(default_factory=lambda: _get_int("RETRIEVAL_MAX_DOCS",  10_000))
    retrieval_export_cap: int = field(default_factory=lambda: _get_int("RETRIEVAL_EXPORT_CAP", 50_000))

    # ── AI Investigation Assistant ───────────────────────────────────────────
    # Optional LLM integration — leave blank to use the built-in deterministic engine.
    # Supported providers: Google Gemini (gemini-*) and OpenAI (gpt-*)
    gemini_api_key: str = field(default_factory=lambda: _get("GEMINI_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: _get("OPENAI_API_KEY", ""))
    gemini_model:   str = field(default_factory=lambda: _get("GEMINI_MODEL", "gemini-2.0-flash"))
    openai_model:   str = field(default_factory=lambda: _get("OPENAI_MODEL", "gpt-4o-mini"))


    # ── Derived Properties ───────────────────────────────────────────────────
    @property
    def es_url(self) -> str:
        """Full Elasticsearch URL."""
        return f"{self.es_scheme}://{self.es_host}:{self.es_port}"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"

    def validate(self) -> List[str]:
        """
        Return a list of validation errors (empty if configuration is valid).
        Called at startup to surface misconfiguration early.
        """
        errors: List[str] = []
        if not self.es_username:
            errors.append("ES_USERNAME is not set")
        if not self.es_password:
            errors.append("ES_PASSWORD is not set")
        if self.es_port <= 0 or self.es_port > 65535:
            errors.append(f"ES_PORT={self.es_port} is invalid")
        if self.batch_size < 1 or self.batch_size > 10_000:
            errors.append(
                f"BATCH_SIZE={self.batch_size} should be between 1 and 10,000"
            )
        return errors

    def ensure_directories(self) -> None:
        """Create required runtime directories if they don't exist."""
        for directory in [
            self.logs_dir,
            self.joblib_cache_dir,
            self.model_save_dir,
            self.project_root / "rules" / "uploaded",
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# ─── Singleton ────────────────────────────────────────────────────────────────
settings = Settings()
