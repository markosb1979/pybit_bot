"""
client_demo.py

Demonstrates and tests all major features and robustness upgrades of BybitClient:
- Robust error handling & retries
- Endpoint-specific rate limiting
- Clean parameter handling
- Dependency injection for session/logger
- Enhanced logging
- .env-driven config for API keys and testnet toggle
- Connection loss/recovery test
"""

import os
import time
import sys
import logging
from typing import Any, Dict

from dotenv import load_dotenv
from pybit_bot.core.client import BybitClient, APICredentials

# --- Load .env variables ---
load_dotenv()

# --- Enhanced Logging Setup ---
class DemoLogger:
    def __init__(self, name="ClientDemo"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s]: %(message)s')
        handler.setFormatter(formatter)
        self.logger.handlers = []
        self.logger.addHandler(handler)
    def info(self, msg, *args): self.logger.info(msg, *args)
    def error(self, msg, *args): self.logger.error(msg, *args)
    def debug(self, msg, *args): self.logger.debug(msg, *args)

# --- Dependency Injection: Custom session (for testing/mocking if needed) ---
import requests
def get_custom_session():
    s = requests.Session()
    s.headers.update({'X-Demo': 'True'})
    return s

def safe_api_call(fn, *args, retries=3, delay=2, **kwargs):
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            print(f"[Retry {attempt+1}/{retries}] {e}")
            time.sleep(delay)
    raise RuntimeError(f"Failed after {retries} attempts: {fn.__name__}")

def main():
    # --- Credentials & testnet from .env ---
    api_key = os.getenv("BYBIT_API_KEY", "")
    api_secret = os.getenv("BYBIT_API_SECRET", "")
    testnet_env = os.getenv("BYBIT_TESTNET", "True").lower()
    testnet = testnet_env in ["1", "true", "yes", "on"]

    if not api_key or not api_secret:
        print("Set BYBIT_API_KEY and BYBIT_API_SECRET in your .env file.")
        return

    creds = APICredentials(api_key=api_key, api_secret=api_secret, testnet=testnet)
    logger = DemoLogger("BybitClientDemo")
    session = get_custom_session()  # For demonstration; in production use default

    # --- Initialize client with dependency injection ---
    client = BybitClient(credentials=creds, logger=logger)
    client.session = session  # Overwrite if needed for testing/mocking

    logger.info("=== Loaded config: testnet=%s ===", testnet)
    logger.info("=== Testing API connection with retries ===")
    if safe_api_call(client.test_connection):
        logger.info("Connection OK.")
    else:
        logger.error("Connection failed.")
        return

    # --- Market Data Tests ---
    symbol = "BTCUSDT"
    logger.info("=== Testing market data endpoints ===")
    logger.info("Server time: %s", safe_api_call(client.get_server_time))
    logger.info("Ticker: %s", safe_api_call(client.get_ticker, symbol))
    logger.info("Orderbook: %s", safe_api_call(client.get_orderbook, symbol, 5))
    logger.info("Wallet balance: %s", safe_api_call(client.get_wallet_balance))

    # --- Parameter Cleaning/Validation Demo ---
    logger.info("=== Testing parameter cleaning (passing None values) ===")
    logger.info("Klines with None start_time/end_time: %s", safe_api_call(client.get_klines, symbol, "1", limit=3, start_time=None, end_time=None))

    # --- Error Handling Demo ---
    logger.info("=== Simulating API error handling (bad endpoint) ===")
    try:
        client._make_request("GET", "/v5/market/this_is_not_real", {}, auth_required=False)
    except Exception as e:
        logger.info(f"Caught API error as expected: {e}")

    # --- Manual Connection Loss/Recovery Test ---
    logger.info("=== Manual connection drop test ===")
    print("Disable your internet NOW. The script will try to fetch ticker every 3 seconds for 3 attempts.")
    print("After 3 failures, restore connection and press Enter to continue.")
    for i in range(3):
        try:
            logger.info("Attempting fetch (should fail if offline):")
            print(safe_api_call(client.get_ticker, symbol, retries=1))
        except Exception as e:
            logger.info(f"Expected error (offline): {e}")
        time.sleep(3)
    input("Restore internet and press Enter to retry: ")
    try:
        logger.info("Retrying ticker fetch (should succeed if reconnected):")
        print(safe_api_call(client.get_ticker, symbol))
        logger.info("Recovered successfully!")
    except Exception as e:
        logger.error(f"Still failing after reconnect: {e}")

    logger.info("=== Demo complete ===")

if __name__ == "__main__":
    main()