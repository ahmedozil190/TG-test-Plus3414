import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

class ExternalProvider:
    def __init__(self, name, url, api_key, profit_margin):
        self.name = name
        self.url = url.rstrip('/') + '/'
        self.api_key = api_key
        self.profit_margin = profit_margin

    async def get_countries(self):
        """Fetch available countries and prices from the provider."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.url}?apiKay={self.api_key}&action=getCountrys"
                logger.info(f"Fetching countries from {self.name}: {url}")
                resp = await client.get(url, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"Response from {self.name}: {data}")
                    return data
                else:
                    logger.warning(f"Failed to fetch countries from {self.name}: {resp.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching countries from {self.name}: {e}")
            return []

    async def buy_number(self, country_code):
        """Order a new number from the provider."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.url}?apiKay={self.api_key}&action=getNumber&country={country_code}"
                resp = await client.get(url, timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # Expected: {"status": "success", "number": "970...", "hash_code": "..."}
                    return data
                return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.error(f"Error buying number from {self.name}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_code(self, hash_code):
        """Fetch the activation code for a purchased number."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.url}?apiKay={self.api_key}&action=getCode&hash_code={hash_code}"
                resp = await client.get(url, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # Expected: {"status": "success", "code": "12345"} or {"status": "pending"}
                    return data
                return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.error(f"Error getting code from {self.name}: {e}")
            return {"status": "error", "message": str(e)}

    def calculate_price(self, provider_price):
        """Calculate selling price based on profit margin."""
        return float(provider_price) * (1 + self.profit_margin / 100.0)
