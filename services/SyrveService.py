import os
from dotenv import load_dotenv
import requests
from typing import Optional, Dict, Any, List

from services.LoggerService import LoggerService

load_dotenv()

class SyrveAPIError(Exception):
    """Custom exception for Syrve API errors."""
    pass

class SyrveService:
    BASE_URL = "https://api-eu.syrve.live/api/1"

    def __init__(self, api_login: str):
        self.api_login = api_login
        self.token: Optional[str] = None

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}" if self.token else None,
            "Content-Type": "application/json"
        }
        headers = {k: v for k, v in headers.items() if v is not None}
        LoggerService.log(main_msg=f"[SyrveService]  post request to {url}", msg_log_db=f"Request to {url} with payload: {payload}")
        response = requests.post(url, json=payload, headers=headers)
        if not response.ok:
            raise SyrveAPIError(f"API Error {response.status_code}: {response.text}")
        return response.json()

    def authenticate(self) -> None:
        response = requests.post(f"{self.BASE_URL}/access_token", json={"apiLogin": self.api_login})
        if not response.ok:
            raise SyrveAPIError(f"Authentication failed: {response.text}")
        data = response.json()
        self.token = data.get("token")
        if not self.token:
            raise SyrveAPIError("Token not found in authentication response.")

    def get_organization_id(self) -> str:
        data = self._post("organizations", {"token": self.token})
        orgs = data.get("organizations", [])
        if not orgs:
            raise SyrveAPIError("No organizations found.")
        return orgs[0]["id"]

    def get_terminal_group_id(self, organization_id: str) -> str:
        data = self._post("terminal_groups", {"organizationIds": [organization_id]})
        terminal_groups = data.get("terminalGroups", [])
        if not terminal_groups or not terminal_groups[0].get("items"):
            raise SyrveAPIError("No terminal groups found.")
        return terminal_groups[0]["items"][0]["id"]

    def get_nomenclature(self, organization_id: str) -> dict:
        return self._post("nomenclature", {"organizationId": organization_id})

    def find_product_by_code(self, nomenclature: dict, code: str) -> Optional[dict]:
        for product in nomenclature.get("products", []):
            if product.get("code") == code:
                return product
        return None

    def create_order(self,
                     organization_id: str,
                     terminal_group_id: str,
                     items: List[Dict[str, Any]],
                     discountsInfo: dict = None) -> Dict[str, Any]:
        
        order_payload = {
            "organizationId": organization_id,
            "terminalGroupId": terminal_group_id,
            "order": {
                "items": items
            }
        }

        if discountsInfo:
            order_payload["order"]["discountsInfo"] = discountsInfo

        
        data = self._post("order/create", order_payload)
        return {
            "correlationId": data.get("correlationId"),
            "orderInfo": data.get("orderInfo")
        }

    def add_payment(self,
                organization_id: str,
                order_id: str,
                payments: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "organizationId": organization_id,
            "orderId": order_id,
            "payments": payments
        }

        # TODO: Delete this in production
        print(f"[SyrveService] Adding payment for order {order_id} with payload: {payload}")
        
        return self._post("order/add_payments", payload)
    
    def close_order(self,
                organization_id: str,
                order_id: str) -> Dict[str, Any]:
        payload = {
            "organizationId" : organization_id,
            "orderId" : order_id
        }
        return self._post("order/close", payload)
    
# Example usage from another service
if __name__ == "__main__":
    api_login = os.getenv("SYRVE_API_LOGIN")
    syrve = SyrveService(api_login=api_login)

    try:
        syrve.authenticate()
        org_id = syrve.get_organization_id()
        term_id = syrve.get_terminal_group_id(org_id)

        nomenclature = syrve.get_nomenclature(org_id)
        product = syrve.find_product_by_code(nomenclature, "PRODUCT-CODE-HERE")

        if not product:
            raise ValueError("Product with given code not found")

        items = [{
            "productId": product["id"],
            "type": "Product",
            "amount": 2.0,
            "price": product["price"]  # Ensure the price is accurate
        }]

    except Exception as e:
        print(f"An error occurred: {e}")