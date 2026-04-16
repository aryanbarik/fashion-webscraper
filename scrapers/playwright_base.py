"""
Base class for scrapers that need a real browser (Playwright) instead of
direct HTTP — used for sites that block headless API calls or JSON endpoints.

Subclasses implement _scrape_page(page, url) and define CATEGORY_URLS.
"""

import asyncio
import httpx

from playwright.async_api import async_playwright, Page, Browser

from .base import BaseScraper, Product

# Realistic browser fingerprint to avoid bot detection
VIEWPORT = {"width": 1280, "height": 900}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class PlaywrightScraper(BaseScraper):
    """
    Drives a real Chromium browser to scrape sites that block direct HTTP.

    The httpx client passed to fetch_products() is used only for image
    downloads in run.py — subclasses should not use it for page fetching.
    """

    # Subclasses set these
    name: str = "playwright"
    CATEGORY_URLS: list[tuple[str, str]] = []  # [(url, category_label), ...]

    # How long to wait (seconds) after page load for JS to settle
    JS_SETTLE_SECONDS: float = 3.0
    # How many times to scroll down to trigger lazy-loaded content
    SCROLL_STEPS: int = 5

    async def fetch_products(self, client: httpx.AsyncClient) -> list[Product]:
        products: list[Product] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport=VIEWPORT,
                locale="en-US",
            )
            for url, label in self.CATEGORY_URLS:
                batch = await self._scrape_with_retry(context, url, label)
                products.extend(batch)
            await browser.close()
        return products

    async def _scrape_with_retry(self, context, url: str, label: str) -> list[Product]:
        page = await context.new_page()
        try:
            print(f"  [{self.name}] {label}: loading {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await self._scroll(page)
            products = await self._scrape_page(page, label)
            print(f"  [{self.name}] {label}: {len(products)} products")
            return products
        except Exception as e:
            print(f"  [{self.name}] {label}: error — {e}")
            return []
        finally:
            await page.close()

    async def _scroll(self, page: Page) -> None:
        """Scroll down incrementally to trigger lazy-loaded product images."""
        for _ in range(self.SCROLL_STEPS):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(self.JS_SETTLE_SECONDS / self.SCROLL_STEPS)

    async def _scrape_page(self, page: Page, category: str) -> list[Product]:
        """Override in subclass to extract products from a loaded page."""
        raise NotImplementedError
