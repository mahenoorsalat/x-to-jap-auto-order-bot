import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JAPClient")

class JAPClient:
    def __init__(self, api_key: str, api_url: str = "https://justanotherpanel.com/api/v2"):
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")

    async def _post(self, payload: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        """Send application/x-www-form-urlencoded POST request to JAP API."""
        payload["key"] = self.api_key
        headers = {"User-Agent": "Automated-SMM-Bridge/1.0"}
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.api_url, data=payload, headers=headers)
            response.raise_for_status()
            
            try:
                return response.json()
            except Exception:
                return {"raw_response": response.text}

    async def add_order(self, service_id: str, link: str, quantity: int) -> Dict[str, Any]:
        """
        Place a new order on JustAnotherPanel.
        Returns API response dict containing 'order' (Order ID) or error details.
        """
        payload = {
            "action": "add",
            "service": str(service_id),
            "link": link,
            "quantity": str(quantity)
        }
        logger.info(f"Placing JAP Order -> Service: {service_id}, Quantity: {quantity}, Link: {link}")
        return await self._post(payload)

    async def get_balance(self) -> Dict[str, Any]:
        """Fetch current JAP account balance and currency."""
        payload = {"action": "balance"}
        return await self._post(payload)

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of an existing order by Order ID."""
        payload = {
            "action": "status",
            "order": str(order_id)
        }
        return await self._post(payload)

    async def get_services(self) -> Dict[str, Any]:
        """Fetch list of all available services on JAP."""
        payload = {"action": "services"}
        return await self._post(payload)
