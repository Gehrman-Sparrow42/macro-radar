"""Abstract BaseFetcher and extensible Strategy Registry for radar_core fetchers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Type

from radar_core.core.models import RawItem

logger = logging.getLogger("radar_core.fetchers")


class BaseFetcher(ABC):
    """Abstract Strategy defining the ingestion interface for all data fetchers."""

    @abstractmethod
    def fetch(self, source_config: dict[str, Any]) -> list[RawItem]:
        """
        Execute ingestion strategy according to source configuration.

        Args:
            source_config: Dictionary containing source parameters (e.g. url, source_name, headers, limit, tags).

        Returns:
            list[RawItem]: Normalized RawItem data transfer objects ready for deduplication and persistence.
        """
        pass


class FetcherRegistry:
    """Registry maintaining available fetcher strategies by unique identifier."""

    _registry: dict[str, Type[BaseFetcher]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a fetcher class under a strategy identifier."""
        def decorator(subclass: Type[BaseFetcher]):
            if not issubclass(subclass, BaseFetcher):
                raise TypeError(f"{subclass.__name__} must inherit from BaseFetcher")
            cls._registry[name.lower()] = subclass
            logger.debug("Registered fetcher strategy: '%s' -> %s", name.lower(), subclass.__name__)
            return subclass
        return decorator

    @classmethod
    def get_fetcher(cls, name: str, **kwargs) -> BaseFetcher:
        """Instantiate and return registered fetcher strategy."""
        key = name.lower()
        if key not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(
                f"Unknown fetcher strategy '{name}'. Available strategies: {available}"
            )
        fetcher_cls = cls._registry[key]
        return fetcher_cls(**kwargs)

    @classmethod
    def list_fetchers(cls) -> list[str]:
        """Return list of all registered fetcher strategy identifiers."""
        return list(cls._registry.keys())


def register_fetcher(name: str):
    """Shortcut decorator for FetcherRegistry.register."""
    return FetcherRegistry.register(name)
