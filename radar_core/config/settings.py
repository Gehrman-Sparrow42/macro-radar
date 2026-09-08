"""Settings and environment management for radar_core using Pydantic Settings."""

import logging
import sys
from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core LLM settings (Hybrid Dual-Provider - Loaded from .env)
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    GEMINI_MODEL: str = "gemini-flash-latest"
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"
    OPENAI_MODEL_HEAVY: str = "gpt-4o"
    OPENAI_MODEL_REASONING: str = "o1"
    DEFAULT_MODEL: str = "gemini-flash-latest"
    LLM_ROUTING_STRATEGY: str = "smart_hybrid"

    # Database settings
    DATABASE_URL: str = "sqlite:///./radar.db"

    # Operational settings
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 4
    BACKOFF_FACTOR: float = 1.5


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of Settings."""
    return Settings()


def setup_logging(log_level: str | None = None) -> logging.Logger:
    """Configure unified logging format across radar_core modules."""
    settings = get_settings()
    level_str = log_level or settings.LOG_LEVEL
    numeric_level = getattr(logging, level_str.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Ensure Windows console supports full UTF-8 output without charmap errors
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("radar_core")
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-runs
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers[0] = handler

    return root_logger
