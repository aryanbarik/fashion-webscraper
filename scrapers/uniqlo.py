import asyncio
import httpx

from .base import BaseScraper, Product

BASE_URL = "https://www.uniqlo.com/us/api/commerce/v5/en/products"
PRODUCT_PAGE_URL = "https://www.uniqlo.com/us/en/products/{product_id}/{color_code}"
PAGE_SIZE = 36

# (category_label, genderId, classId)
# Gender IDs: Men=22211, Women=22210, Kids=22212, Baby=22213
# Class IDs:  Men T-Shirts & Sweats=23305, Women T-Shirts & Sweats=23295
CATEGORIES = [
    ("men_tops",   22211, 23305),
    ("women_tops", 22210, 23295),
]


class UniqloScraper(BaseScraper):
    name = "uniqlo"

    async def fetch_products(self, client: httpx.AsyncClient) -> list[Product]:
        products: list[Product] = []
        for label, gender_id, class_id in CATEGORIES:
            products.extend(await self._scrape_category(client, label, gender_id, class_id))
        return products

    async def _scrape_category(
        self, client: httpx.AsyncClient, label: str, gender_id: int, class_id: int
    ) -> list[Product]:
        print(f"  [uniqlo] {label} ...")
        first = await self._fetch_page(client, gender_id, class_id, offset=0)
        total = first.get("result", {}).get("pagination", {}).get("total", 0)

        all_items = list(first.get("result", {}).get("items", []))
        offsets = range(PAGE_SIZE, total, PAGE_SIZE)
        pages = await asyncio.gather(
            *[self._fetch_page(client, gender_id, class_id, o) for o in offsets]
        )
        for page in pages:
            all_items.extend(page.get("result", {}).get("items", []))

        products = []
        seen: set[str] = set()
        for item in all_items:
            p = self._parse_item(item, label)
            if p and p.product_id not in seen:
                seen.add(p.product_id)
                products.append(p)

        print(f"  [uniqlo] {label}: {len(products)} products")
        return products

    async def _fetch_page(
        self, client: httpx.AsyncClient, gender_id: int, class_id: int, offset: int
    ) -> dict:
        r = await client.get(
            BASE_URL,
            params={
                "path": f"{gender_id},{class_id},,",
                "genderId": gender_id,
                "offset": offset,
                "limit": PAGE_SIZE,
                "imageRatio": "3x4",
                "httpFailure": "true",
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    def _parse_item(self, item: dict, category: str) -> Product | None:
        product_id = item.get("productId", "")
        name = item.get("name", "")
        color_code = item.get("representativeColorDisplayCode", "00")
        main_images = item.get("images", {}).get("main", {})

        image_url = (
            main_images.get(color_code, {}).get("image")
            or next((v.get("image") for v in main_images.values() if v.get("image")), "")
        )

        if not product_id or not image_url:
            return None

        return Product(
            product_id=product_id,
            name=name,
            product_url=PRODUCT_PAGE_URL.format(product_id=product_id, color_code=color_code),
            image_url=image_url,
            category=category,
            source=self.name,
        )
