import os
from dotenv import load_dotenv
from services.DBService import init_db
from services.SyncBridge import SyncBridge

load_dotenv()

SMARTKASA_PHONE = os.getenv("SMARTKASA_PHONE")
SMARTKASA_PASSWORD = os.getenv("SMARTKASA_PASSWORD")
SMARTKASA_API_KEY = os.getenv("SMARTKASA_API_KEY")
SYRVE_API_LOGIN = os.getenv("SYRVE_API_LOGIN")

if __name__ == "__main__":
    init_db()
    smartkasa_config = {
        "phone_number": SMARTKASA_PHONE,
        "password": SMARTKASA_PASSWORD,
        "api_key": SMARTKASA_API_KEY
    }

    syrve_config = {
        "api_login": SYRVE_API_LOGIN
    }

    bridge = SyncBridge(smartkasa_conf=smartkasa_config, syrve_conf=syrve_config)
    bridge.sync_last_receipts()
