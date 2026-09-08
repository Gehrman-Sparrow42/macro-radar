"""Fetchers package exposing base classes, registry, and concrete strategies."""

from radar_core.core.fetchers.base import (
    BaseFetcher,
    FetcherRegistry,
    register_fetcher,
)
from radar_core.core.fetchers.rss_fetcher import RSSFetcher
from radar_core.core.fetchers.crawl_fetcher import CrawlFetcher

__all__ = [
    "BaseFetcher",
    "FetcherRegistry",
    "register_fetcher",
    "RSSFetcher",
    "CrawlFetcher",
]
