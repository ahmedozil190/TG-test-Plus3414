import httpx
import logging
import asyncio

logger = logging.getLogger(__name__)

class ExternalProvider:
    def __init__(self, name, url, api_key, profit_margin, server_type="standard", extra_id=None):
        self.name = name
        self.url = url.rstrip('/') + '/'
        self.api_key = api_key
        self.profit_margin = profit_margin
        self.server_type = server_type
        self.extra_id = extra_id

    def get_base_params(self, action):
        """Prepare base parameters for API calls."""
        if self.server_type == "lion":
            params = {
                "action": action,
                "apiKey": self.api_key,
                "YourID": self.extra_id
            }
        else:
            # Standard (Spider/Max-TG)
            params = {
                "action": action,
                "apiKay": self.api_key
            }
        return params

    async def get_countries(self):
        """Fetch available countries and prices from the provider."""
        try:
            async with httpx.AsyncClient() as client:
                action = "country_info" if self.server_type == "lion" else "getCountrys"
                params = self.get_base_params(action)
                
                logger.info(f"Fetching countries from {self.name}: {self.url} with {params}")
                resp = await client.get(self.url, params=params, timeout=15.0)
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

    async def get_balance(self):
        """Fetch the current balance from the provider."""
        try:
            async with httpx.AsyncClient() as client:
                action = "getBalance"
                params = self.get_base_params(action)
                
                logger.info(f"Fetching balance from {self.name}: {self.url}")
                resp = await client.get(self.url, params=params, timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # Standard API usually returns balance in data['balance'] or similar. 
                    # If lion returns something else, we handle it if needed.
                    if "balance" in data:
                        return str(data["balance"])
                    elif "Balance" in data:
                        return str(data["Balance"])
                    return "N/A"
                else:
                    return "Error"
        except Exception as e:
            logger.error(f"Error fetching balance from {self.name}: {e}")
            return "Error"

    async def buy_number(self, country_code):
        """Order a new number from the provider."""
        try:
            async with httpx.AsyncClient() as client:
                params = self.get_base_params("getNumber")
                if self.server_type == "lion":
                    params["country_code"] = country_code
                else:
                    params["country"] = country_code
                
                resp = await client.get(self.url, params=params, timeout=20.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data
                return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.error(f"Error buying number from {self.name}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_code(self, hash_code, number=None):
        """Fetch the activation code for a purchased number."""
        try:
            async with httpx.AsyncClient() as client:
                params = self.get_base_params("getCode")
                if self.server_type == "lion":
                    params["number"] = number
                else:
                    params["hash_code"] = hash_code
                
                resp = await client.get(self.url, params=params, timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data
                return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.error(f"Error getting code from {self.name}: {e}")
            return {"status": "error", "message": str(e)}

    def calculate_price(self, provider_price):
        """Calculate selling price based on profit margin."""
        return float(provider_price) * (1 + self.profit_margin / 100.0)
