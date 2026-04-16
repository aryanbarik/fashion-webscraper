"""
Generic Shopify scraper.

Works on any store that runs Shopify. Pass a list of (store_url, category_label)
tuples. The store_url should be the root domain, e.g. "https://www.gymshark.com".

Shopify exposes /products.json on every storefront. Pagination is handled via
the Link header (cursor-based) when limit=250 is used.
"""

import asyncio
import re
import httpx

from .base import BaseScraper, Product

PAGE_SIZE = 250  # Shopify's maximum


class ShopifyScraper(BaseScraper):
    name = "shopify"

    def __init__(self, stores: list[tuple[str, str]]):
        """
        Args:
            stores: list of (store_url, category_label), e.g.
                    [("https://www.gymshark.com", "gymshark"),
                     ("https://www.allbirds.com", "allbirds")]
        """
        self.stores = stores

    async def fetch_products(self, client: httpx.AsyncClient) -> list[Product]:
        results = await asyncio.gather(
            *[self._scrape_store(client, url, label) for url, label in self.stores]
        )
        return [p for batch in results for p in batch]

    async def _scrape_store(
        self, client: httpx.AsyncClient, store_url: str, label: str
    ) -> list[Product]:
        store_url = store_url.rstrip("/")
        print(f"  [shopify] {label} ({store_url}) ...")
        products: list[Product] = []
        seen: set[str] = set()

        # Shopify cursor pagination via Link header
        url = f"{store_url}/products.json"
        params: dict = {"limit": PAGE_SIZE}

        while url:
            try:
                r = await client.get(url, params=params, timeout=20)
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                print(f"  [shopify] {label}: HTTP {e.response.status_code}, stopping")
                break
            except Exception as e:
                print(f"  [shopify] {label}: {e}, stopping")
                break

            data = r.json()
            for item in data.get("products", []):
                p = self._parse_item(item, label, store_url)
                if p and p.product_id not in seen:
                    seen.add(p.product_id)
                    products.append(p)

            # Advance cursor from Link header, e.g.:
            # <https://store.com/products.json?...page_info=xxx&limit=250>; rel="next"
            url = self._next_url(r.headers.get("Link", ""))
            params = {}  # cursor already embedded in the next URL

        print(f"  [shopify] {label}: {len(products)} products")
        return products

    def _parse_item(self, item: dict, category: str, store_url: str) -> Product | None:
        product_id = str(item.get("id", ""))
        name = item.get("title", "")
        handle = item.get("handle", "")
        images = item.get("images", [])

        if not product_id or not handle or not images:
            return None

        return Product(
            product_id=f"{category}_{product_id}",
            name=name,
            product_url=f"{store_url}/products/{handle}",
            image_url=images[0]["src"],
            category=category,
            source=self.name,
        )

    @staticmethod
    def _next_url(link_header: str) -> str:
        """Parse the 'next' URL from a Shopify Link header."""
        match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        return match.group(1) if match else ""
