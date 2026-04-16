from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import httpx


@dataclass
class Product:
    product_id: str
    name: str
    product_url: str
    image_url: str
    category: str
    source: str
    scraped_at: str = ""

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class BaseScraper(ABC):
    name: str  # set by each subclass

    @abstractmethod
    async def fetch_products(self, client: httpx.AsyncClient) -> list[Product]:
        """Return all products this scraper can find."""
        ...
