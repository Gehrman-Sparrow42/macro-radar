"""Settings configuration for radar_macro application."""

from functools import lru_cache
import logging
import sys
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class MacroSettings(BaseSettings):
    """Configuration specific to the Macro & Regulatory Intelligence Radar."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core LLM APIs (Hybrid Dual-Provider - Loaded from .env)
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    GEMINI_MODEL: str = "gemini-flash-latest"
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"
    OPENAI_MODEL_HEAVY: str = "gpt-4o"
    OPENAI_MODEL_REASONING: str = "o1"
    DEFAULT_MODEL: str = "gemini-flash-latest"
    LLM_ROUTING_STRATEGY: str = "smart_hybrid"

    # Dedicated Macro Database (Segregated from other radar databases)
    DATABASE_URL: str = "sqlite:///./macro_radar.db"

    # Ingestion & Operational Settings
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    MIN_CONTENT_LENGTH: int = 45
    DEFAULT_POLL_INTERVAL: int = 3600  # 1 hour
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 1.5


@lru_cache()
def get_macro_settings() -> MacroSettings:
    """Return cached singleton instance of MacroSettings."""
    return MacroSettings()


def setup_macro_logging(log_level: str | None = None) -> logging.Logger:
    """Setup logging format for radar_macro with Windows UTF-8 safety."""
    settings = get_macro_settings()
    level_str = log_level or settings.LOG_LEVEL
    numeric_level = getattr(logging, level_str.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [macro] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger("radar_macro")
    logger.setLevel(numeric_level)

    if not logger.handlers:
        logger.addHandler(handler)
    else:
        logger.handlers[0] = handler

    return logger
