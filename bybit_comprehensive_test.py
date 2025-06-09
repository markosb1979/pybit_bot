#!/usr/bin/env python3
"""
Comprehensive Bybit API Test Script
Tests all core functionality on testnet using parameters from .env
"""

import os
import sys
import time
import json
import asyncio
import websockets
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Add project root to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import the Bybit client modules
from pybit_bot.core.client import BybitClient, APICredentials
from pybit_bot.utils.logger import Logger
from pybit_bot.exceptions import BybitAPIError, AuthenticationError

# Initialize logger
logger = Logger("ComprehensiveTest")

class Config:
    """Configuration loaded from .env file"""
    
    def __init__(self):
        # Load .env file
        if not load_dotenv():
            logger.warning("No .env file found or failed to load")
            
        # API credentials
        self.api_key = os.getenv("BYBIT_API_KEY")
        self.api_secret = os.getenv("BYBIT_API_SECRET")
        self.testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        
        # Trading configuration
        self.symbol = os.getenv("TRADING_SYMBOL", "BTCUSDT")
        self.position_size = float(os.getenv("POSITION_SIZE", "0.001"))
        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "0.02"))
        self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "0.04"))
        
        # Risk management
        self.max_daily_loss = float(os.getenv("MAX_DAILY_LOSS", "0.05"))
        self.max_open_positions = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
        self.min_balance_threshold = float(os.getenv("MIN_BALANCE_THRESHOLD", "100.0"))
        
        # Validate required fields
        self._validate()
        
    def _validate(self):
        """Validate configuration"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found in .env file")
            
        logger.info(f"Configuration loaded:")
        logger.info(f"  Trading on: {'Testnet' if self.testnet else 'Mainnet'}")
        logger.info(f"  Symbol: {self.symbol}")
        logger.info(f"  Position Size: {self.position_size}")
        logger.info(f"  Stop Loss: {self.stop_loss_pct*100}%")
        logger.info(f"  Take Profit: {self.take_profit_pct*100}%")
        
    def get_credentials(self):
        """Get API credentials object"""
        return APICredentials(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet
        )


class WebSocketClient:
    """WebSocket client for Bybit"""
    
    def __init__(self, is_testnet=True):
        self.is_testnet = is_testnet
        self.ws_url = (
            "wss://stream-testnet.bybit.com/v5/public/linear" 
            if is_testnet else 
            "wss://stream.bybit.com/v5/public/linear"
        )
        self.ws = None
        self.running = False
        
    async def connect(self, symbol="BTCUSDT", channels=None):
        """Connect to WebSocket and subscribe to channels"""
        if channels is None:
            channels = ["kline.1", "tickers"]
            
        logger.info(f"Connecting to WebSocket at {self.ws_url}")
        
        try:
            self.ws = await websockets.connect(self.ws_url)
            self.running = True
            
            # Subscribe to channels
            subscribe_msg = {
                "op": "subscribe",
                "args": [f"{channel}.{symbol}" for channel in channels]
            }
            
            await self.ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {channels} for {symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {str(e)}")
            return False
            
    async def listen(self, duration_seconds=60):
        """Listen for WebSocket messages for a specified duration"""
        if not self.ws:
            logger.error("WebSocket not connected")
            return
            
        start_time = time.time()
        message_count = 0
        
        logger.info(f"Listening for WebSocket messages for {duration_seconds} seconds")
        
        try:
            while self.running and (time.time() - start_time) < duration_seconds:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                    message_count += 1
                    
                    # Parse and display the message
                    data = json.loads(message)
                    
                    if "topic" in data:
                        topic = data["topic"]
                        
                        if "kline" in topic:
                            # Format kline data
                            kline = data.get("data", [{}])[0]
                            timestamp = datetime.fromtimestamp(int(kline.get("start", 0)) / 1000)
                            logger.info(f"Kline: {timestamp} - O: {kline.get('open')} H: {kline.get('high')} L: {kline.get('low')} C: {kline.get('close')}")
                            
                        elif "ticker" in topic:
                            # Format ticker data
                            ticker = data.get("data", {})
                            logger.info(f"Ticker: Last: {ticker.get('lastPrice')} - 24h Change: {ticker.get('price24hPcnt')}%")
                            
                        else:
                            # Just print the topic
                            logger.info(f"Received message for topic: {topic}")
                    
                except asyncio.TimeoutError:
                    continue
                    
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {str(e)}")
            
        finally:
            logger.info(f"WebSocket listener finished. Received {message_count} messages")
            
    async def close(self):
        """Close the WebSocket connection"""
        if self.ws:
            self.running = False
            await self.ws.close()
            logger.info("WebSocket connection closed")


def test_api_credentials(client):
    """Test API credentials"""
    logger.info("\n" + "="*50)
    logger.info("TESTING API CREDENTIALS")
    logger.info("="*50)
    
    try:
        result = client.test_connection()
        if result:
            logger.info("✅ API credentials are valid")
            return True
        else:
            logger.error("❌ API connection test failed")
            return False
    except AuthenticationError as e:
        logger.error(f"❌ Authentication failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return False


def test_signature(client):
    """Test API signature generation"""
    logger.info("\n" + "="*50)
    logger.info("TESTING API SIGNATURE")
    logger.info("="*50)
    
    try:
        # Test with a simple authenticated request
        result = client.get_wallet_balance()
        
        if result:
            # Extract some account info for display
            account_type = result.get("list", [{}])[0].get("accountType", "Unknown")
            total_equity = result.get("list", [{}])[0].get("totalEquity", "0")
            
            logger.info(f"✅ Signature generation successful")
            logger.info(f"Account Type: {account_type}")
            logger.info(f"Total Equity: {total_equity}")
            return True
        else:
            logger.error("❌ Failed to get wallet balance")
            return False
    except Exception as e:
        logger.error(f"❌ Signature test failed: {str(e)}")
        return False


def test_get_historical_klines(client, config):
    """Test retrieving historical kline data"""
    symbol = config.symbol
    interval = "1"  # 1 minute
    count = 2000
    
    logger.info("\n" + "="*50)
    logger.info(f"TESTING HISTORICAL KLINES (Getting {count} {interval}m {symbol} bars)")
    logger.info("="*50)
    
    try:
        # We need to make multiple requests since the API limit is 1000 bars per request
        all_klines = []
        batches = (count + 999) // 1000  # Ceiling division to get number of batches
        
        logger.info(f"Fetching {batches} batches of klines (max 1000 per batch)")
        
        for i in range(batches):
            batch_count = min(1000, count - len(all_klines))
            
            # If we already have klines, use the oldest one's timestamp as end time for next batch
            end_time = None
            if all_klines:
                end_time = int(all_klines[-1][0]) - 1  # Convert to int and subtract 1ms
            
            logger.info(f"Fetching batch {i+1}/{batches} ({batch_count} bars)" + 
                      (f" ending at {datetime.fromtimestamp(end_time/1000)}" if end_time else ""))
            
            batch = client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=batch_count,
                end_time=end_time
            )
            
            if not batch:
                logger.warning(f"No klines returned for batch {i+1}")
                break
                
            # Bybit returns most recent first, so we append to maintain that order
            all_klines.extend(batch)
            
            # If we didn't get a full batch, we've reached the limit of available data
            if len(batch) < batch_count:
                logger.info(f"Reached end of available data after {len(all_klines)} bars")
                break
                
            # Small delay to avoid rate limiting
            time.sleep(0.5)
        
        if all_klines:
            # Log the first and last klines
            first_kline = all_klines[0]
            last_kline = all_klines[-1]
            
            first_time = datetime.fromtimestamp(int(first_kline[0]) / 1000)
            last_time = datetime.fromtimestamp(int(last_kline[0]) / 1000)
            
            logger.info(f"✅ Successfully retrieved {len(all_klines)} klines")
            logger.info(f"First kline: {first_time} - O: {first_kline[1]} H: {first_kline[2]} L: {first_kline[3]} C: {first_kline[4]}")
            logger.info(f"Last kline: {last_time} - O: {last_kline[1]} H: {last_kline[2]} L: {last_kline[3]} C: {last_kline[4]}")
            
            # Optionally save to CSV file
            csv_file = f"{symbol}_{interval}m_klines.csv"
            try:
                with open(csv_file, 'w') as f:
                    f.write("timestamp,open,high,low,close,volume,turnover\n")
                    for k in all_klines:
                        f.write(f"{k[0]},{k[1]},{k[2]},{k[3]},{k[4]},{k[5]},{k[6]}\n")
                logger.info(f"Saved klines to {csv_file}")
            except Exception as e:
                logger.error(f"Failed to save klines to CSV: {str(e)}")
            
            return True
        else:
            logger.error("❌ Failed to retrieve any klines")
            return False
            
    except Exception as e:
        logger.error(f"❌ Historical klines test failed: {str(e)}")
        return False


def test_wallet_balance(client):
    """Test wallet balance retrieval"""
    logger.info("\n" + "="*50)
    logger.info("TESTING WALLET BALANCE")
    logger.info("="*50)
    
    try:
        result = client.get_wallet_balance()
        
        if result and result.get("list"):
            account = result["list"][0]
            coins = account.get("coin", [])
            
            logger.info(f"Account Type: {account.get('accountType')}")
            logger.info(f"Total Equity: {account.get('totalEquity')}")
            
            # Display balances for each coin
            for coin in coins:
                if float(coin.get("walletBalance", 0)) > 0:
                    logger.info(f"{coin.get('coin')}: "
                                f"Wallet Balance = {coin.get('walletBalance')}, "
                                f"Available = {coin.get('availableBalance')}")
            
            return True
        else:
            logger.error("❌ Failed to get wallet balance")
            return False
            
    except Exception as e:
        logger.error(f"❌ Wallet balance test failed: {str(e)}")
        return False


def test_market_orders(client, config):
    """Test market order placement and closing"""
    symbol = config.symbol
    position_size = config.position_size
    
    logger.info("\n" + "="*50)
    logger.info(f"TESTING MARKET ORDERS ({symbol})")
    logger.info("="*50)
    
    try:
        # Get current ticker price
        ticker = client.get_ticker(symbol)
        current_price = float(ticker.get("lastPrice", 0))
        
        if current_price <= 0:
            logger.error(f"❌ Invalid current price: {current_price}")
            return False
            
        logger.info(f"Current {symbol} price: {current_price}")
        
        # 1. Test BUY MARKET order
        logger.info("\n--- Testing BUY MARKET order ---")
        buy_order_id = f"test_market_buy_{int(time.time())}"
        
        # Calculate stop loss and take profit based on configuration
        if "BTC" in symbol:
            # Round to appropriate precision for BTC (0.5 for price)
            stop_loss_price = round(current_price * (1 - config.stop_loss_pct), 0)
            take_profit_price = round(current_price * (1 + config.take_profit_pct), 0)
        else:
            # For other coins, use 2 decimal places
            stop_loss_price = round(current_price * (1 - config.stop_loss_pct), 2)
            take_profit_price = round(current_price * (1 + config.take_profit_pct), 2)
            
        logger.info(f"Using position size: {position_size}")
        logger.info(f"Stop Loss: {stop_loss_price} (${current_price - stop_loss_price:.2f} below entry)")
        logger.info(f"Take Profit: {take_profit_price} (${take_profit_price - current_price:.2f} above entry)")
        
        buy_result = client.place_order(
            symbol=symbol,
            side="Buy",
            order_type="Market",
            qty=str(position_size),
            order_link_id=buy_order_id,
            stop_loss=str(stop_loss_price),
            take_profit=str(take_profit_price)
        )
        
        if not buy_result:
            logger.error("❌ Failed to place buy market order")
            return False
            
        logger.info(f"✅ Buy market order placed successfully")
        logger.info(f"Order ID: {buy_result.get('orderId')}")
        logger.info(f"Order Link ID: {buy_order_id}")
        
        # Wait for the order to be filled
        logger.info("Waiting for buy order to be filled...")
        time.sleep(3)
        
        # Check position after buy
        positions = client.get_positions(symbol)
        position = None
        
        for pos in positions:
            if pos.get("symbol") == symbol and float(pos.get("size", 0)) > 0:
                position = pos
                break
                
        if not position:
            logger.warning("❓ No position found after buy market order")
        else:
            logger.info(f"Position after buy: {position.get('side')} {position.get('size')} @ {position.get('avgPrice')}")
            logger.info(f"Stop Loss: {position.get('stopLoss')}")
            logger.info(f"Take Profit: {position.get('takeProfit')}")
        
        # 2. Test SELL MARKET order (close position)
        logger.info("\n--- Testing SELL MARKET order (closing position) ---")
        
        # If we have a position, get the size for closing
        if position:
            close_qty = position.get("size")
        else:
            close_qty = str(position_size)
            
        sell_order_id = f"test_market_sell_{int(time.time())}"
        
        sell_result = client.place_order(
            symbol=symbol,
            side="Sell",
            order_type="Market",
            qty=close_qty,
            order_link_id=sell_order_id
        )
        
        if not sell_result:
            logger.error("❌ Failed to place sell market order")
            return False
            
        logger.info(f"✅ Sell market order placed successfully")
        logger.info(f"Order ID: {sell_result.get('orderId')}")
        logger.info(f"Order Link ID: {sell_order_id}")
        
        # Wait for the order to be filled
        logger.info("Waiting for sell order to be filled...")
        time.sleep(3)
        
        # Check position after sell
        positions = client.get_positions(symbol)
        position_after_sell = None
        
        for pos in positions:
            if pos.get("symbol") == symbol and float(pos.get("size", 0)) != 0:
                position_after_sell = pos
                break
                
        if position_after_sell:
            logger.warning(f"⚠️ Position still exists after sell: {position_after_sell.get('side')} {position_after_sell.get('size')}")
        else:
            logger.info("✅ Position closed successfully")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Market order test failed: {str(e)}")
        return False


def test_limit_orders(client, config):
    """Test limit order placement and cancellation"""
    symbol = config.symbol
    position_size = config.position_size
    
    logger.info("\n" + "="*50)
    logger.info(f"TESTING LIMIT ORDERS ({symbol})")
    logger.info("="*50)
    
    try:
        # Get current ticker price
        ticker = client.get_ticker(symbol)
        current_price = float(ticker.get("lastPrice", 0))
        
        if current_price <= 0:
            logger.error(f"❌ Invalid current price: {current_price}")
            return False
            
        logger.info(f"Current {symbol} price: {current_price}")
        
        # 1. Test BUY LIMIT order (5% below current price)
        logger.info("\n--- Testing BUY LIMIT order ---")
        buy_price = round(current_price * 0.95, 2)  # 5% below market
        buy_order_id = f"test_limit_buy_{int(time.time())}"
        
        buy_result = client.place_order(
            symbol=symbol,
            side="Buy",
            order_type="Limit",
            qty=str(position_size),
            price=str(buy_price),
            order_link_id=buy_order_id
        )
        
        if not buy_result:
            logger.error("❌ Failed to place buy limit order")
            return False
            
        logger.info(f"✅ Buy limit order placed successfully")
        logger.info(f"Order ID: {buy_result.get('orderId')}")
        logger.info(f"Order Link ID: {buy_order_id}")
        logger.info(f"Price: {buy_price} (5% below market)")
        
        # Wait a moment
        time.sleep(2)
        
        # Cancel the buy limit order
        logger.info("Cancelling buy limit order...")
        cancel_buy_result = client.cancel_order(
            symbol=symbol,
            order_link_id=buy_order_id
        )
        
        if not cancel_buy_result:
            logger.error("❌ Failed to cancel buy limit order")
        else:
            logger.info(f"✅ Buy limit order cancelled successfully")
        
        # 2. Test SELL LIMIT order (5% above current price)
        logger.info("\n--- Testing SELL LIMIT order ---")
        sell_price = round(current_price * 1.05, 2)  # 5% above market
        sell_order_id = f"test_limit_sell_{int(time.time())}"
        
        sell_result = client.place_order(
            symbol=symbol,
            side="Sell",
            order_type="Limit",
            qty=str(position_size),
            price=str(sell_price),
            order_link_id=sell_order_id
        )
        
        if not sell_result:
            logger.error("❌ Failed to place sell limit order")
            return False
            
        logger.info(f"✅ Sell limit order placed successfully")
        logger.info(f"Order ID: {sell_result.get('orderId')}")
        logger.info(f"Order Link ID: {sell_order_id}")
        logger.info(f"Price: {sell_price} (5% above market)")
        
        # Wait a moment
        time.sleep(2)
        
        # Cancel the sell limit order
        logger.info("Cancelling sell limit order...")
        cancel_sell_result = client.cancel_order(
            symbol=symbol,
            order_link_id=sell_order_id
        )
        
        if not cancel_sell_result:
            logger.error("❌ Failed to cancel sell limit order")
        else:
            logger.info(f"✅ Sell limit order cancelled successfully")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Limit order test failed: {str(e)}")
        return False


async def test_websocket(config, duration_seconds=60):
    """Test WebSocket functionality"""
    symbol = config.symbol
    
    logger.info("\n" + "="*50)
    logger.info("TESTING WEBSOCKET CONNECTION")
    logger.info("="*50)
    
    ws_client = WebSocketClient(is_testnet=config.testnet)
    
    # Connect and subscribe
    connected = await ws_client.connect(symbol=symbol, channels=["kline.1", "tickers"])
    
    if not connected:
        logger.error("Failed to connect to WebSocket")
        return False
    
    # Listen for messages
    logger.info(f"Listening for WebSocket messages for {duration_seconds} seconds...")
    listen_task = asyncio.create_task(ws_client.listen(duration_seconds))
    
    # Wait for the specified duration
    await asyncio.sleep(duration_seconds)
    
    # Close the connection
    await ws_client.close()
    await listen_task
    
    logger.info("WebSocket test completed")
    return True


async def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("STARTING COMPREHENSIVE BYBIT API TEST")
    logger.info(f"Test Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info("=" * 60)
    
    try:
        # Load configuration from .env file
        config = Config()
        
        # Initialize the client
        client = BybitClient(config.get_credentials(), logger)
        
        # Run tests in sequence
        test_sequence = [
            ("API Credentials", lambda: test_api_credentials(client)),
            ("API Signature", lambda: test_signature(client)),
            ("Wallet Balance", lambda: test_wallet_balance(client)),
            ("Historical Klines", lambda: test_get_historical_klines(client, config)),
            ("Market Orders", lambda: test_market_orders(client, config)),
            ("Limit Orders", lambda: test_limit_orders(client, config)),
            ("WebSocket", lambda: asyncio.create_task(test_websocket(config, duration_seconds=60)))
        ]
        
        results = {}
        
        for test_name, test_func in test_sequence:
            logger.info(f"\n{'='*60}\nRUNNING TEST: {test_name}\n{'='*60}")
            
            try:
                if test_name == "WebSocket":
                    # Handle WebSocket test differently since it's async
                    ws_task = test_func()
                    await ws_task
                    result = True
                else:
                    result = test_func()
                
                results[test_name] = result
                status = "✅ PASSED" if result else "❌ FAILED"
                logger.info(f"{test_name} test: {status}")
                
            except Exception as e:
                logger.error(f"Error in {test_name} test: {str(e)}")
                results[test_name] = False
            
            # Small delay between tests
            time.sleep(1)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        
        all_passed = True
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            logger.info("\n🎉 ALL TESTS PASSED! The Bybit API client is working correctly.")
        else:
            logger.warning("\n⚠️ SOME TESTS FAILED. Please review the logs.")
        
    except Exception as e:
        logger.error(f"Test script failed: {str(e)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")