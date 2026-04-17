"""
Fashion image scraper — entrypoint.

Add or remove scrapers from SCRAPERS below to control what gets scraped.
Re-runs are incremental: already-saved products are skipped.

Images are uploaded to S3. Configure the bucket and credentials in .env.
"""

import asyncio
import json
import os
import httpx
import boto3

from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

from scrapers.uniqlo import UniqloScraper
from scrapers.shopify import ShopifyScraper
from scrapers.gymshark import GymsharkScraper

load_dotenv()

OUTPUT_DIR = Path("output")
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


def s3_client():
    return boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def load_existing(path: Path) -> tuple[list[dict], set[str]]:
    if path.exists():
        records = json.loads(path.read_text())
        return records, {r["product_id"] for r in records}
    return [], set()


def save_metadata(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2))


async def fetch_and_upload(
    http: httpx.AsyncClient,
    s3,
    bucket: str,
    image_url: str,
    s3_key: str,
) -> str | None:
    """Download image bytes and upload directly to S3. Returns the S3 URL on success."""
    try:
        r = await http.get(image_url, timeout=20)
        r.raise_for_status()

        content_type = r.headers.get("content-type", "image/jpeg")
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=r.content,
            ContentType=content_type,
        )

        region = os.environ["AWS_REGION"]
        return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"

    except Exception as e:
        print(f"  [!] Failed {image_url}: {e}")
        return None


async def main() -> None:
    bucket = os.environ.get("S3_BUCKET")
    if not bucket or bucket == "your-bucket-name":
        raise ValueError("Set S3_BUCKET in your .env file before running.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing, existing_ids = load_existing(METADATA_FILE)
    s3 = s3_client()

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as http:
        # Fetch products from all scrapers
        all_new = []
        for scraper in SCRAPERS:
            print(f"\n[{scraper.name}] Fetching products...")
            products = await scraper.fetch_products(http)
            new = [p for p in products if p.product_id not in existing_ids]
            all_new.extend(new)
            print(f"[{scraper.name}] {len(new)} new / {len(products) - len(new)} already saved")

        if not all_new:
            print("\n[=] Nothing new to upload.")
            return

        # Build upload tasks
        print(f"\n[>] Uploading {len(all_new)} images to s3://{bucket}...")
        records = []
        tasks = []
        for product in all_new:
            ext = Path(urlparse(product.image_url).path).suffix or ".jpg"
            s3_key = f"images/{product.product_id}{ext}"
            d = product.to_dict()
            d["s3_key"] = s3_key
            records.append(d)
            tasks.append(fetch_and_upload(http, s3, bucket, product.image_url, s3_key))

        s3_urls = await asyncio.gather(*tasks)

    uploaded = 0
    for record, url in zip(records, s3_urls):
        if url:
            record["s3_url"] = url
            uploaded += 1
        else:
            record["s3_url"] = None

    print(f"[+] Uploaded {uploaded}/{len(records)} images")

    combined = existing + records
    save_metadata(combined, METADATA_FILE)
    print(f"[+] Metadata saved to {METADATA_FILE} ({len(combined)} total records)")


if __name__ == "__main__":
    asyncio.run(main())
