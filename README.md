# fashion-webscraper

Scrapes product images and links from fashion retail websites. Built as a data collection tool for clothing similarity search.

## How it works

The scraper uses an adapter pattern — there's a shared core that handles downloading images and saving metadata, and a thin site-specific adapter for each retailer that knows how to fetch product data from that site.

Three types of adapters are supported:

- **Direct API** (`scrapers/uniqlo.py`) — Some sites expose an internal REST API that the browser calls. We call it directly with `httpx`, which is fast and doesn't require a browser.
- **Shopify** (`scrapers/shopify.py`) — Any store running on Shopify exposes a public `/products.json` endpoint. One adapter covers thousands of brands.
- **Playwright** (`scrapers/playwright_base.py`, `scrapers/gymshark.py`) — Sites that block direct HTTP requests get scraped using a real Chromium browser via Playwright. The browser renders the page like a human would, then we extract product data from the DOM.

Runs are **incremental** — already-saved products are skipped, so re-running only fetches what's new.

## Output

```
output/
  metadata.json       # one record per product
  images/
    E465185-000.jpg   # named by product_id
    ...
```

Each record in `metadata.json` looks like:

```json
{
  "product_id": "E465185-000",
  "name": "AIRism Cotton Oversized T-Shirt | Half-Sleeve",
  "product_url": "https://www.uniqlo.com/us/en/products/E465185-000/00",
  "image_url": "https://image.uniqlo.com/UQ/ST3/us/imagesgoods/465185/item/usgoods_00_465185_3x4.jpg",
  "category": "men_tops",
  "source": "uniqlo",
  "scraped_at": "2026-04-16T19:08:46.559821+00:00",
  "local_image_path": "output/images/E465185-000.jpg"
}
```

| Field | Description |
|---|---|
| `product_id` | Unique identifier (source-scoped) |
| `name` | Product display name |
| `product_url` | Link to the product page on the retailer's site |
| `image_url` | Direct URL of the product image |
| `category` | Category label set in the adapter |
| `source` | Which scraper produced this record |
| `scraped_at` | UTC timestamp |
| `local_image_path` | Path to the downloaded image file |

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Running

```bash
python run.py
```

To control which sites are scraped, edit the `SCRAPERS` list at the top of `run.py`.

## Adding a new site

**Shopify store** — add one line to the `ShopifyScraper` stores list in `run.py`:

```python
ShopifyScraper(stores=[
    ("https://www.allbirds.com", "allbirds"),
    ("https://www.newstore.com", "newstore"),  # add here
])
```

**Non-Shopify site** — create a new file in `scrapers/`, subclass `BaseScraper` (or `PlaywrightScraper` if the site blocks direct HTTP), implement `fetch_products()`, and add an instance to `SCRAPERS` in `run.py`.
