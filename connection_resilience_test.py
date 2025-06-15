"""
connection_resilience_test.py

Continuously fetches market data using BybitClient.
Simulate a disconnect by disabling your network for 10 seconds—script will keep retrying and resume when reconnected.
"""

import os
import time
import sys
import logging
from dotenv import load_dotenv
from pybit_bot.core.client import BybitClient, APICredentials

# --- Load .env ---
load_dotenv()

# --- Enhanced Logging ---
class DemoLogger:
    def __init__(self, name="ResilienceTest"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s]: %(message)s')
        handler.setFormatter(formatter)
        self.logger.handlers = []
        self.logger.addHandler(handler)
    def info(self, msg, *args): self.logger.info(msg, *args)
    def error(self, msg, *args): self.logger.error(msg, *args)
    def debug(self, msg, *args): self.logger.debug(msg, *args)

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
    logger = DemoLogger("ResilienceTest")
    client = BybitClient(credentials=creds, logger=logger)

    symbol = "BTCUSDT"
    logger.info("Starting continuous ticker pull for symbol: %s (testnet=%s)", symbol, testnet)
    logger.info("Disable your internet connection at any time to simulate a disconnect. Script will auto-resume.")

    last_error = None
    recovered_once = False
    while True:
        try:
            ticker = client.get_ticker(symbol)
            logger.info("Ticker: %s", ticker)
            if last_error:
                logger.info("Connection restored and data received!")
                last_error = None
                recovered_once = True
        except Exception as e:
            if not last_error:
                logger.error("Network/API error: %s", e)
                logger.info("Will retry every 3 seconds until connection is restored...")
            last_error = str(e)
        time.sleep(3)

if __name__ == "__main__":
    main()