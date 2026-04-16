"""
Fashion image scraper — entrypoint.

Add or remove scrapers from SCRAPERS below to control what gets scraped.
Re-runs are incremental: already-saved products are skipped.
"""

import asyncio
import json
import httpx

from pathlib import Path
from urllib.parse import urlparse

from scrapers.uniqlo import UniqloScraper
from scrapers.shopify import ShopifyScraper
from scrapers.gymshark import GymsharkScraper

OUTPUT_DIR = Path("output")
IMAGES_DIR = OUTPUT_DIR / "images"
METADATA_FILE = OUTPUT_DIR / "metadata.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# --- Configure scrapers here ---
SCRAPERS = [
    UniqloScraper(),
    ShopifyScraper(stores=[
        ("https://www.allbirds.com", "allbirds"),
    ]),
    GymsharkScraper(),
]
# --------------------------------


def load_existing(path: Path) -> tuple[list[dict], set[str]]:
    if path.exists():
        records = json.loads(path.read_text())
        return records, {r["product_id"] for r in records}
    return [], set()


def save_metadata(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2))


async def download_image(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        r = await client.get(url, timeout=20)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  [!] Failed {url}: {e}")
        return False


async def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    existing, existing_ids = load_existing(METADATA_FILE)

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        # Fetch products from all scrapers
        all_new = []
        for scraper in SCRAPERS:
            print(f"\n[{scraper.name}] Fetching products...")
            products = await scraper.fetch_products(client)
            new = [p for p in products if p.product_id not in existing_ids]
            all_new.extend(new)
            print(f"[{scraper.name}] {len(new)} new / {len(products) - len(new)} already saved")

        if not all_new:
            print("\n[=] Nothing new to download.")
            return

        # Assign local image paths
        records = []
        for product in all_new:
            ext = Path(urlparse(product.image_url).path).suffix or ".jpg"
            local_path = str(IMAGES_DIR / f"{product.product_id}{ext}")
            d = product.to_dict()
            d["local_image_path"] = local_path
            records.append(d)

        # Download images
        print(f"\n[>] Downloading {len(records)} images...")
        results = await asyncio.gather(
            *[download_image(client, r["image_url"], Path(r["local_image_path"])) for r in records]
        )

    saved = sum(results)
    print(f"[+] Downloaded {saved}/{len(records)} images")

    combined = existing + records
    save_metadata(combined, METADATA_FILE)
    print(f"[+] Metadata saved to {METADATA_FILE} ({len(combined)} total records)")


if __name__ == "__main__":
    asyncio.run(main())
