"""
Demo script to print Bybit USDT Perpetual (BTCUSDT) instrument info using pybit_ex_official.
"""

from pybit._v5_market import MarketHTTP

def main():
    # Create client for testnet (set testnet=False for mainnet)
    client = MarketHTTP(testnet=True)

    # Query instrument info for BTCUSDT USDT perpetual
    result = client.get_instruments_info(category="linear", symbol="BTCUSDT")

    # Pretty print the result
    from pprint import pprint
    print("Instrument Info for BTCUSDT (USDT Perpetual):")
    pprint(result)

if __name__ == "__main__":
    main()