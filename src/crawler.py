from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin, urlparse

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeout, async_playwright

from .config import settings

logger = logging.getLogger(__name__)


def _normalize_domain_to_url(domain: str) -> str:
    domain = domain.strip()
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    return domain


def _same_site(base_netloc: str, candidate: str) -> bool:
    try:
        netloc = urlparse(candidate).netloc.lower()
    except ValueError:
        return False
    base_netloc = base_netloc.lower().removeprefix("www.")
    netloc = netloc.removeprefix("www.")
    return netloc == "" or netloc == base_netloc


async def _discover_subpage_urls(page: Page, base_url: str) -> list[str]:
    """Rank same-site links by keyword relevance, return top matches (deduped)."""
    base_netloc = urlparse(base_url).netloc
    hrefs: list[str] = await page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )

    scored: dict[str, int] = {}
    for href in hrefs:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if not _same_site(base_netloc, absolute):
            continue
        path = urlparse(absolute).path.lower()
        score = sum(1 for kw in settings.subpage_keywords if kw in path)
        if score > 0:
            # Strip fragments/query for dedup, keep the highest score seen
            clean = absolute.split("#")[0]
            scored[clean] = max(scored.get(clean, 0), score)

    ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    return [url for url, _ in ranked[: settings.max_subpages_per_domain]]


async def _fetch_rendered_html(browser: Browser, url: str) -> str | None:
    context = await browser.new_context(user_agent=settings.user_agent)
    page = await context.new_page()
    try:
        await page.goto(url, timeout=settings.page_load_timeout_ms, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=settings.page_load_timeout_ms)
        except PlaywrightTimeout:
            # Some sites (chat widgets, analytics beacons) never go fully idle.
            # domcontentloaded content is already usable at this point.
            logger.debug("networkidle timeout on %s — using DOM as-is", url)
        html = await page.content()
        return html
    except PlaywrightTimeout:
        logger.warning("Timed out loading %s", url)
        return None
    except Exception as exc:  # noqa: BLE001 - crawler must never crash the pipeline
        logger.warning("Failed to load %s: %s", url, exc)
        return None
    finally:
        await context.close()


async def crawl_domain(domain: str) -> dict[str, str]:
    """Fetch homepage + discovered subpages for a single domain.

    Returns {absolute_url: raw_html}. Homepage is always attempted first;
    subpages are best-effort (a subpage failure never aborts the domain).
    """
    base_url = _normalize_domain_to_url(domain)
    pages: dict[str, str] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=settings.headless)
        try:
            context = await browser.new_context(user_agent=settings.user_agent)
            home_page = await context.new_page()
            try:
                await home_page.goto(
                    base_url, timeout=settings.page_load_timeout_ms, wait_until="domcontentloaded"
                )
                try:
                    await home_page.wait_for_load_state(
                        "networkidle", timeout=settings.page_load_timeout_ms
                    )
                except PlaywrightTimeout:
                    pass
                pages[base_url] = await home_page.content()
                subpage_urls = await _discover_subpage_urls(home_page, base_url)
            except PlaywrightTimeout:
                logger.error("Homepage timed out for %s", domain)
                subpage_urls = []
            finally:
                await context.close()

            for url in subpage_urls:
                await asyncio.sleep(settings.request_delay_seconds)
                html = await _fetch_rendered_html(browser, url)
                if html:
                    pages[url] = html
        finally:
            await browser.close()

    return pages