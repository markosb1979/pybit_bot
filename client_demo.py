"""
client_demo.py

Demonstrates the resilience and robustness of the upgraded BybitClient.
- Loads API credentials and testnet toggle from .env.
- Continuously fetches ticker data every 3 seconds.
- Handles connection drops: if you disconnect your network, the script will retry and resume automatically.
- Logs all steps and recovers gracefully.

Instructions:
1. Set your BYBIT_API_KEY, BYBIT_API_SECRET, and BYBIT_TESTNET in a .env file.
2. Run this script: python client_demo.py
3. While running, disconnect your internet for ~10 seconds, then reconnect.
4. Observe how the script logs errors and recovers once connection is back.
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
    def __init__(self, name="ClientDemo"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s]: %(message)s')
        handler.setFormatter(formatter)
        self.logger.handlers = []
        self.logger.addHandler(handler)
    def info(self, msg, *a): self.logger.info(msg, *a)
    def error(self, msg, *a): self.logger.error(msg, *a)
    def debug(self, msg, *a): self.logger.debug(msg, *a)
    def warning(self, msg, *a): self.logger.warning(msg, *a)

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
    logger = DemoLogger("ClientDemo")
    client = BybitClient(credentials=creds, logger=logger)

    symbol = "BTCUSDT"
    logger.info("Starting continuous ticker pull for symbol: %s (testnet=%s)", symbol, testnet)
    logger.info("Disable your internet connection at any time to simulate a disconnect. Script will auto-resume.")

    last_error = None
    while True:
        try:
            ticker = client.get_ticker(symbol)
            logger.info("Ticker: %s", ticker)
            if last_error:
                logger.info("Connection restored and data received!")
                last_error = None
        except Exception as e:
            if not last_error:
                logger.error("Network/API error: %s", e)
                logger.info("Will retry every 3 seconds until connection is restored...")
            last_error = str(e)
        time.sleep(3)

if __name__ == "__main__":
    main()