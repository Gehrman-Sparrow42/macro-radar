"""RSS/Atom feed ingestion strategy using feedparser."""

import logging
import re
from typing import Any
from bs4 import BeautifulSoup
import feedparser
import httpx

from radar_core.core.fetchers.base import BaseFetcher, register_fetcher
from radar_core.core.models import RawItem

logger = logging.getLogger("radar_core.fetchers.rss")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 RadarCore/1.0"
)


def _clean_html_content(raw_html: str) -> str:
    """Convert HTML snippet to clean, normalized readable text."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for elem in soup(["script", "style", "nav", "header", "footer"]):
        elem.extract()
    text = soup.get_text(separator="\n")
    # Clean multiple blank lines
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


@register_fetcher("rss")
class RSSFetcher(BaseFetcher):
    """Fetcher strategy for parsing XML/RSS/Atom feeds."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 20):
        self.user_agent = user_agent
        self.timeout = timeout

    def fetch(self, source_config: dict[str, Any]) -> list[RawItem]:
        """
        Fetch and parse an RSS or Atom feed.

        Expected source_config keys:
            - url: URL of the RSS feed.
            - source_name: Identifier for the source (e.g. "ECB_Press_Releases", "HackerNews").
            - limit (optional): Max items to parse (default: 30).
            - clean_html (optional): Clean HTML tags from content (default: True).
        """
        feed_url = source_config.get("url") or source_config.get("feed_url")
        if not feed_url:
            raise ValueError("source_config must contain a 'url' key for RSSFetcher")

        source_name = source_config.get("source_name") or "rss_feed"
        limit = source_config.get("limit", 30)
        clean_html = source_config.get("clean_html", True)

        logger.info("Fetching RSS feed from: %s (source: %s)", feed_url, source_name)

        try:
            # We fetch using httpx with a modern browser User-Agent to avoid 403 blocks
            headers = {"User-Agent": self.user_agent}
            response = httpx.get(feed_url, headers=headers, timeout=self.timeout, follow_redirects=True)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except httpx.HTTPStatusError as http_err:
            logger.warning("HTTP error %d fetching feed %s. Skipping.", http_err.response.status_code, feed_url)
            return []
        except Exception as exc:
            logger.warning("Failed direct HTTP fetch for %s, falling back to feedparser.parse: %s", feed_url, exc)
            try:
                import socket
                socket.setdefaulttimeout(self.timeout)
                parsed = feedparser.parse(feed_url)
            except Exception as fallback_exc:
                logger.error("Error parsing RSS feed %s: %s", feed_url, fallback_exc)
                return []

        if parsed.bozo and not parsed.entries:
            logger.warning(
                "Feedparser indicated malformed XML for %s: %s",
                feed_url,
                getattr(parsed, "bozo_exception", "Unknown XML parsing error"),
            )

        items: list[RawItem] = []
        entries = parsed.entries[:limit] if limit else parsed.entries

        for entry in entries:
            try:
                title = getattr(entry, "title", "Untitled").strip()
                link = getattr(entry, "link", "").strip() or feed_url

                # Extract best available content body
                content_text = ""
                if hasattr(entry, "content") and entry.content:
                    content_text = entry.content[0].get("value", "")
                elif hasattr(entry, "summary"):
                    content_text = entry.summary
                elif hasattr(entry, "description"):
                    content_text = entry.description

                if clean_html:
                    content_text = _clean_html_content(content_text)
                else:
                    content_text = content_text.strip()

                # If content is too short or identical to title, include title in text
                if not content_text:
                    content_text = title

                metadata = {
                    "published": getattr(entry, "published", None) or getattr(entry, "updated", None),
                    "author": getattr(entry, "author", None),
                    "tags": [tag.get("term") for tag in getattr(entry, "tags", []) if isinstance(tag, dict)],
                    "feed_title": getattr(parsed.feed, "title", source_name),
                }

                raw_item = RawItem(
                    source_name=source_name,
                    url=link,
                    title=title,
                    content_text=content_text,
                    raw_metadata=metadata,
                )
                items.append(raw_item)
            except Exception as item_exc:
                logger.debug("Skipping unparseable RSS entry: %s", item_exc)
                continue

        logger.info("Successfully fetched %d items from %s", len(items), feed_url)
        return items
