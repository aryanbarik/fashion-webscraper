"""
Gymshark scraper.

Gymshark runs on Shopify but blocks /products.json, so we use a real browser
instead. Products are rendered as <li> cards inside a product grid.
"""

from playwright.async_api import Page

from .base import Product
from .playwright_base import PlaywrightScraper


class GymsharkScraper(PlaywrightScraper):
    name = "gymshark"

    CATEGORY_URLS = [
        ("https://www.gymshark.com/collections/t-shirts-tops/mens",   "gymshark_mens_tops"),
        ("https://www.gymshark.com/collections/t-shirts-tops/womens", "gymshark_womens_tops"),
    ]

    JS_SETTLE_SECONDS = 5.0
    SCROLL_STEPS = 6

    async def _scrape_page(self, page: Page, category: str) -> list[Product]:
        # Wait for at least one product image link to appear
        await page.wait_for_selector("a[href*='/products/'] img", timeout=15_000)

        # Each product has two <a href="/products/..."> tags:
        # one wrapping the image, one wrapping the title.
        # We select the ones that contain an <img> to get both URL and image src.
        raw = await page.evaluate("""
            () => {
                const links = document.querySelectorAll("a[href*='/products/']");
                return Array.from(links)
                    .filter(a => a.querySelector("img"))
                    .map(a => {
                        const img = a.querySelector("img");
                        return {
                            href: a.href,
                            src:  img.src || img.dataset.src || "",
                            name: img.alt || "",
                        };
                    });
            }
        """)

        products: list[Product] = []
        seen: set[str] = set()

        for item in raw:
            href = item.get("href", "")
            src  = item.get("src", "")
            name = item.get("name", "")

            if not href or not src:
                continue

            # Derive a stable product ID from the URL slug
            slug = href.rstrip("/").split("/")[-1]
            product_id = f"gymshark_{slug}"

            # Strip Shopify image size suffixes (e.g. _480x480) for full-res
            src = _strip_size_suffix(src)

            if product_id not in seen:
                seen.add(product_id)
                products.append(Product(
                    product_id=product_id,
                    name=name,
                    product_url=href,
                    image_url=src,
                    category=category,
                    source=self.name,
                ))

        return products


def _strip_size_suffix(url: str) -> str:
    """Remove Shopify thumbnail size suffixes like _480x480 or _1x1 from image URLs."""
    import re
    return re.sub(r"_\d+x\d*(?=\.\w{3,4}(\?|$))", "", url)
