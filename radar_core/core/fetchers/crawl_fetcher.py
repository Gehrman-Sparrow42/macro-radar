"""Headless and dynamic crawling strategy using crawl4ai with resilient HTTP/BS4 fallback."""

import asyncio
import logging
import re
from typing import Any
from bs4 import BeautifulSoup
import httpx

from radar_core.core.fetchers.base import BaseFetcher, register_fetcher
from radar_core.core.models import RawItem

logger = logging.getLogger("radar_core.fetchers.crawl")

DEFAULT_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}


def _extract_semantic_text_and_title(html: str) -> tuple[str, str]:
    """Extract clean title and structured text/markdown representation from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title = ""
    title_elem = soup.find("title") or soup.find("h1")
    if title_elem:
        title = title_elem.get_text().strip()

    # Remove non-content elements
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "button"]):
        element.extract()

    # Priority to article or main content if present
    content_root = soup.find("main") or soup.find("article") or soup.find("div", {"id": re.compile(r"content|main", re.I)}) or soup.body or soup

    # Format headings and paragraphs
    lines: list[str] = []
    for el in content_root.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        txt = el.get_text().strip()
        if not txt:
            continue
        if el.name in ["h1", "h2", "h3", "h4"]:
            lines.append(f"\n### {txt}\n")
        elif el.name == "li":
            lines.append(f"- {txt}")
        else:
            lines.append(txt)

    full_text = "\n\n".join(lines).strip()
    if not full_text:
        full_text = content_root.get_text(separator="\n").strip()

    # Normalize whitespace
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    return title or "Untitled Document", full_text


async def _crawl_with_crawl4ai(url: str, css_selector: str | None = None) -> tuple[str, str, dict[str, Any]]:
    """Attempt dynamic headless crawl using crawl4ai."""
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError:
        raise RuntimeError("crawl4ai package is not installed")

    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url, css_selector=css_selector)
        if not result.success:
            raise RuntimeError(f"crawl4ai failed for {url}: {result.error_message}")

        # Crawl4ai provides extracted clean markdown
        content_markdown = getattr(result, "markdown", None) or getattr(result, "extracted_content", "") or ""
        metadata = getattr(result, "metadata", {}) or {}
        title = metadata.get("title", "") or ""

        if not title:
            # Try to grab first heading
            m = re.search(r"^#\s+(.+)$", content_markdown, re.MULTILINE)
            if m:
                title = m.group(1).strip()

        return title or "Untitled Document", content_markdown, {"crawler": "crawl4ai", **metadata}


def _crawl_with_httpx(url: str, timeout: int = 30) -> tuple[str, str, dict[str, Any]]:
    """Resilient direct HTTP fallback extractor."""
    with httpx.Client(headers=DEFAULT_BROWSER_HEADERS, timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        title, content = _extract_semantic_text_and_title(resp.text)
        return title, content, {"crawler": "httpx_fallback", "status_code": resp.status_code}


@register_fetcher("crawl")
@register_fetcher("web")
class CrawlFetcher(BaseFetcher):
    """Dynamic web crawler strategy with crawl4ai engine and resilient fallback."""

    def __init__(self, default_timeout: int = 30):
        self.default_timeout = default_timeout

    def fetch(self, source_config: dict[str, Any]) -> list[RawItem]:
        """
        Fetch web page content dynamically.

        Expected source_config keys:
            - url (or urls: list[str]): Target URL(s).
            - source_name: Identifier for the source.
            - css_selector (optional): Restrict extraction to CSS query.
            - timeout (optional): Request timeout in seconds.
        """
        raw_urls = source_config.get("url") or source_config.get("urls")
        if not raw_urls:
            raise ValueError("source_config must contain 'url' or 'urls' for CrawlFetcher")

        urls: list[str] = [raw_urls] if isinstance(raw_urls, str) else list(raw_urls)
        source_name = source_config.get("source_name") or "web_crawl"
        css_selector = source_config.get("css_selector")
        timeout = source_config.get("timeout", self.default_timeout)

        items: list[RawItem] = []

        for target_url in urls:
            logger.info("Crawling target URL: %s [source=%s]", target_url, source_name)
            title = ""
            content_text = ""
            meta: dict[str, Any] = {}

            # Attempt crawl4ai dynamic execution
            try:
                # Run async crawler safely in event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # Running in existing loop, use an isolated thread or future
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(lambda: asyncio.run(_crawl_with_crawl4ai(target_url, css_selector)))
                        title, content_text, meta = future.result(timeout=timeout)
                else:
                    title, content_text, meta = asyncio.run(_crawl_with_crawl4ai(target_url, css_selector))

                logger.info("Successfully scraped via crawl4ai: %s (%d chars)", target_url, len(content_text))
            except Exception as crawl_err:
                logger.warning(
                    "crawl4ai not available or encountered error (%s). Falling back to direct HTTP fetch.",
                    crawl_err,
                )
                try:
                    title, content_text, meta = _crawl_with_httpx(target_url, timeout=timeout)
                    logger.info("Successfully scraped via HTTP fallback: %s (%d chars)", target_url, len(content_text))
                except Exception as http_err:
                    logger.error("Failed all crawl strategies for %s: %s", target_url, http_err)
                    continue

            if content_text:
                item = RawItem(
                    source_name=source_name,
                    url=target_url,
                    title=title or target_url,
                    content_text=content_text,
                    raw_metadata=meta,
                )
                items.append(item)

        return items
