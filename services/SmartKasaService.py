import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

load_dotenv()

class SmartKasaAPIError(Exception):
    """Custom exception for SmartKasa API errors."""
    pass


class SmartKasaService:
    BASE_URL = "https://core.smartkasa.ua"

    def __init__(self, phone_number: str, password: str, api_key: str):
        self.phone_number = phone_number
        self.password = password
        self.api_key = api_key
        self.access_token: Optional[str] = None

    def _get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'X-Api-Key': self.api_key
        }
        if include_auth and self.access_token:
            headers['Authorization'] = f"Bearer {self.access_token}"
        return headers

    def authenticate(self) -> None:
        url = f"{self.BASE_URL}/api/v1/auth/sessions"
        payload = {
            "session": {
                "phone_number": self.phone_number,
                "password": self.password
            }
        }
        response = requests.post(url, headers=self._get_headers(include_auth=False), json=payload)
        if response.status_code == 201:
            self.access_token = response.json()['data']['access']
        else:
            raise SmartKasaAPIError(f"Auth failed: {response.status_code}, {response.text}")

    def get_invoices(self, date_start: str = None, date_end: str=None) -> List[Dict]:
        url = f"{self.BASE_URL}/api/v1/pos/receipts"
        params = {
            'date_start': date_start,
            'date_end': date_end
        }
        response = requests.get(url, headers=self._get_headers(), params=params)

        if response.status_code == 200:
            return response.json().get('data', [])
        else:
            raise SmartKasaAPIError(f"Get invoices failed: {response.status_code}, {response.text}")

    def get_invoices_all_pages(self, date_start: str = None, date_end: str = None) -> List[Dict]:
        url = f"{self.BASE_URL}/api/v1/pos/receipts"
        all_data = []
        page = 1

        while True:
            params = {
                'date_start': date_start,
                'date_end': date_end,
                'page': page
            }
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code != 200:
                raise SmartKasaAPIError(f"Get invoices failed: {response.status_code}, {response.text}")

            data = response.json().get('data', [])
            all_data.extend(data)
            meta = response.json().get('meta', {})
            next_page = meta.get('next_page')
            if not next_page:
                break
            page = next_page

        return all_data

    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        url = f"{self.BASE_URL}/api/v1/inventory/products/{product_id}"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return response.json().get('data')
        else:
            print(f"[get_product_by_id] Error: {response.status_code}, {response.text}")
            return None

    def filter_receipts_by_date(self, receipts: list, date_from: str = None, date_to: str = None) -> list:
        def parse_date(dt_str):
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

        filtered = []
        for receipt in receipts:
            created = parse_date(receipt["created_at"])
            if date_from:
                from_dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
                if created < from_dt:
                    continue
            if date_to:
                to_dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
                if created > to_dt:
                    continue
            filtered.append(receipt)
        return filtered

if __name__ == "__main__":
    
    SMARTKASA_PHONE = os.getenv("SMARTKASA_PHONE")
    SMARTKASA_PASSWORD = os.getenv("SMARTKASA_PASSWORD")
    SMARTKASA_API_KEY = os.getenv("SMARTKASA_API_KEY")
    
    smartkasa = SmartKasaService(
        phone_number=SMARTKASA_PHONE,
        password=SMARTKASA_PASSWORD,
        api_key=SMARTKASA_API_KEY
    )

    try:
        smartkasa.authenticate()

        yesterday = datetime.now() - timedelta(days=100)
        date_str = yesterday.strftime('%Y-%m-%d')

        print(f"Отримання чеків ...")
        receipts = smartkasa.get_invoices()

        if not receipts:
            print("Чеків не знайдено.")
        else:
            print(f"Знайдено {len(receipts)} чеків:")
            print(receipts[0])
            for r in receipts: 
                print(f"- ID: {r.get('id')}, Сума: {r.get('total_amount')} грн, Дата: {r.get('created_at')}")
                print(f"- payment_transactions: {r.get('payment_transactions')[0].get("transaction_type_id")}")

    except SmartKasaAPIError as e:
        print(f"Помилка API: {e}")
    except Exception as ex:
        print(f"Невідома помилка: {ex}")
