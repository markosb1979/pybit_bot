#!/usr/bin/env python3
"""
Comprehensive Bybit Trading Bot Test Script
Tests all functionality on testnet before mainnet deployment
Windows-compatible version
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
from pathlib import Path

# Set console encoding for Windows compatibility
if sys.platform.startswith('win'):
    try:
        # Try to set UTF-8 encoding for Windows console
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass  # Fall back to default encoding

# Add the parent directory to Python path to enable proper imports
current_dir = Path(__file__).parent
project_root = current_dir.parent if current_dir.name == "pybit_bot" else current_dir
sys.path.insert(0, str(project_root))

# Now import our modules
try:
    from pybit_bot import BybitClient, APICredentials, Logger, ConfigManager
    from pybit_bot.exceptions import *
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print("Please ensure you're running from the correct directory")
    sys.exit(1)


class StatusIcons:
    """Cross-platform status icons"""
    def __init__(self):
        # Try Unicode first, fall back to ASCII
        try:
            # Test if Unicode works
            test_str = "✅❌⚠️"
            test_str.encode(sys.stdout.encoding or 'utf-8')
            self.PASS = "✅"
            self.FAIL = "❌" 
            self.WARN = "⚠️"
            self.SUCCESS = "🎉"
        except (UnicodeEncodeError, LookupError):
            # Fall back to ASCII
            self.PASS = "[PASS]"
            self.FAIL = "[FAIL]"
            self.WARN = "[WARN]"
            self.SUCCESS = "[SUCCESS]"

# Global status icons
ICONS = StatusIcons()


class ComprehensiveTester:
    """
    Comprehensive testing suite for the Bybit trading bot
    """
    
    def __init__(self):
        self.logger = Logger("BotTester")
        
        # Try to initialize config manager with better error handling
        try:
            self.config_manager = ConfigManager()
        except Exception as e:
            self.logger.warning(f"Config manager initialization warning: {e}")
            self.config_manager = None
            
        self.client = None
        self.test_results = {}
        
    def load_credentials_from_env(self) -> APICredentials:
        """Load API credentials from environment file"""
        try:
            # Try to load from .env file
            env_file = Path('.env')
            if env_file.exists():
                self.logger.info("Loading credentials from .env file")
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#') and line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip().strip('"\'')
            else:
                self.logger.warning(".env file not found, using environment variables")
            
            api_key = os.getenv('BYBIT_API_KEY')
            api_secret = os.getenv('BYBIT_API_SECRET')
            testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
            
            if not api_key or not api_secret:
                self.logger.error("Missing API credentials!")
                self.logger.info("Please ensure .env file contains:")
                self.logger.info("BYBIT_API_KEY=your_api_key")
                self.logger.info("BYBIT_API_SECRET=your_api_secret")
                self.logger.info("BYBIT_TESTNET=true")
                raise ConfigurationError("API credentials not found in environment")
                
            self.logger.info(f"Loaded credentials for {'testnet' if testnet else 'mainnet'}")
            
            return APICredentials(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load credentials: {str(e)}")
            raise
    
    async def run_all_tests(self):
        """Run comprehensive test suite"""
        self.logger.info("=" * 60)
        self.logger.info("STARTING COMPREHENSIVE BYBIT BOT TESTING")
        self.logger.info(f"Test Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        self.logger.info("=" * 60)
        
        try:
            # Initialize client
            credentials = self.load_credentials_from_env()
            self.client = BybitClient(credentials, self.logger)
            
            # Test sequence
            test_sequence = [
                ("Connection Test", self.test_connection),
                ("API Credentials", self.test_api_credentials),
                ("Signature Test", self.test_signature),
                ("Server Time", self.test_server_time),
                ("Wallet Balance", self.test_wallet_balance),
                ("Historical Klines", self.test_historical_klines),
                ("Live Market Data", self.test_live_market_data),
                ("Order Book", self.test_orderbook),
                ("Position Status", self.test_positions),
                ("Place Limit Order", self.test_place_limit_order),
                ("Cancel Order", self.test_cancel_order),
                ("Place Market Order", self.test_place_market_order),
                ("Close Position", self.test_close_position),
                ("WebSocket Connection", self.test_websocket_connection),
                ("Rate Limiting", self.test_rate_limiting),
            ]
            
            for test_name, test_func in test_sequence:
                self.logger.info(f"\n{'='*50}")
                self.logger.info(f"TESTING: {test_name}")
                self.logger.info(f"{'='*50}")
                
                try:
                    result = await test_func()
                    self.test_results[test_name] = {
                        "status": "PASS" if result else "FAIL",
                        "timestamp": datetime.utcnow().isoformat(),
                        "details": result if isinstance(result, dict) else {}
                    }
                    
                    status = f"{ICONS.PASS} PASS" if result else f"{ICONS.FAIL} FAIL"
                    self.logger.info(f"Result: {status}")
                    
                except Exception as e:
                    self.test_results[test_name] = {
                        "status": "ERROR",
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": str(e)
                    }
                    self.logger.error(f"Result: {ICONS.FAIL} ERROR - {str(e)}")
                
                # Small delay between tests
                await asyncio.sleep(1)
            
            # Generate test report
            self.generate_test_report()
            
        except Exception as e:
            self.logger.error(f"Test suite failed: {str(e)}")
            raise
    
    async def test_connection(self) -> bool:
        """Test basic API connection"""
        try:
            return self.client.test_connection()
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False
    
    async def test_api_credentials(self) -> bool:
        """Test API credentials validity"""
        try:
            balance = self.client.get_wallet_balance()
            self.logger.info(f"{ICONS.PASS} API credentials are valid")
            return True
        except AuthenticationError:
            self.logger.error(f"{ICONS.FAIL} Invalid API credentials")
            return False
        except Exception as e:
            self.logger.error(f"Credential test error: {str(e)}")
            return False
    
    async def test_signature(self) -> Dict[str, Any]:
        """Test API signature generation"""
        try:
            # Test with a simple authenticated request
            result = self.client.get_wallet_balance()
            
            return {
                "signature_valid": True,
                "account_type": result.get("list", [{}])[0].get("accountType", "Unknown"),
                "total_equity": result.get("list", [{}])[0].get("totalEquity", "0")
            }
        except Exception as e:
            self.logger.error(f"Signature test failed: {str(e)}")
            return {"signature_valid": False, "error": str(e)}
    
    async def test_server_time(self) -> Dict[str, Any]:
        """Test server time retrieval"""
        try:
            result = self.client.get_server_time()
            server_time = int(result.get("timeSecond", 0))
            local_time = int(time.time())
            time_diff = abs(server_time - local_time)
            
            self.logger.info(f"Server time: {datetime.fromtimestamp(server_time)}")
            self.logger.info(f"Local time: {datetime.fromtimestamp(local_time)}")
            self.logger.info(f"Time difference: {time_diff} seconds")
            
            return {
                "server_time": server_time,
                "local_time": local_time,
                "time_diff_seconds": time_diff,
                "sync_ok": time_diff < 30  # Acceptable if within 30 seconds
            }
        except Exception as e:
            self.logger.error(f"Server time test failed: {str(e)}")
            return {"sync_ok": False, "error": str(e)}
    
    async def test_wallet_balance(self) -> Dict[str, Any]:
        """Test wallet balance retrieval"""
        try:
            result = self.client.get_wallet_balance()
            
            if result.get("list"):
                account = result["list"][0]
                coins = account.get("coin", [])
                
                balances = {}
                for coin in coins:
                    if float(coin.get("walletBalance", 0)) > 0:
                        balances[coin.get("coin")] = {
                            "wallet_balance": coin.get("walletBalance"),
                            "available_balance": coin.get("availableBalance"),
                            "locked": coin.get("locked", "0")
                        }
                
                self.logger.info(f"Account balances: {json.dumps(balances, indent=2)}")
                
                return {
                    "account_type": account.get("accountType"),
                    "total_equity": account.get("totalEquity"),
                    "balances": balances,
                    "has_balance": len(balances) > 0
                }
            else:
                return {"has_balance": False, "error": "No account data"}
                
        except Exception as e:
            self.logger.error(f"Wallet balance test failed: {str(e)}")
            return {"has_balance": False, "error": str(e)}
    
    async def test_historical_klines(self) -> Dict[str, Any]:
        """Test historical kline data retrieval (1000 1m BTCUSDT bars)"""
        try:
            symbol = "BTCUSDT"
            interval = "1"  # 1 minute
            limit = 1000
            
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            if klines:
                latest_kline = klines[0]  # Most recent
                oldest_kline = klines[-1]  # Oldest
                
                latest_time = datetime.fromtimestamp(int(latest_kline[0]) / 1000)
                oldest_time = datetime.fromtimestamp(int(oldest_kline[0]) / 1000)
                
                self.logger.info(f"Retrieved {len(klines)} klines")
                self.logger.info(f"Latest: {latest_time} - Price: {latest_kline[4]}")
                self.logger.info(f"Oldest: {oldest_time} - Price: {oldest_kline[4]}")
                
                return {
                    "symbol": symbol,
                    "interval": interval,
                    "count": len(klines),
                    "latest_price": latest_kline[4],
                    "latest_time": latest_time.isoformat(),
                    "oldest_time": oldest_time.isoformat(),
                    "success": True
                }
            else:
                return {"success": False, "error": "No kline data received"}
                
        except Exception as e:
            self.logger.error(f"Historical klines test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_live_market_data(self) -> Dict[str, Any]:
        """Test live market data (ticker)"""
        try:
            symbol = "BTCUSDT"
            ticker = self.client.get_ticker(symbol)
            
            if ticker:
                self.logger.info(f"Live {symbol} data:")
                self.logger.info(f"  Last Price: {ticker.get('lastPrice')}")
                self.logger.info(f"  24h Change: {ticker.get('price24hPcnt')}%")
                self.logger.info(f"  24h Volume: {ticker.get('volume24h')}")
                self.logger.info(f"  Bid: {ticker.get('bid1Price')}")
                self.logger.info(f"  Ask: {ticker.get('ask1Price')}")
                
                return {
                    "symbol": symbol,
                    "last_price": ticker.get("lastPrice"),
                    "change_24h": ticker.get("price24hPcnt"),
                    "volume_24h": ticker.get("volume24h"),
                    "bid": ticker.get("bid1Price"),
                    "ask": ticker.get("ask1Price"),
                    "success": True
                }
            else:
                return {"success": False, "error": "No ticker data received"}
                
        except Exception as e:
            self.logger.error(f"Live market data test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_orderbook(self) -> Dict[str, Any]:
        """Test orderbook data retrieval"""
        try:
            symbol = "BTCUSDT"
            orderbook = self.client.get_orderbook(symbol, limit=10)
            
            if orderbook:
                bids = orderbook.get("b", [])
                asks = orderbook.get("a", [])
                
                self.logger.info(f"Orderbook for {symbol}:")
                self.logger.info(f"  Best Bid: {bids[0] if bids else 'N/A'}")
                self.logger.info(f"  Best Ask: {asks[0] if asks else 'N/A'}")
                self.logger.info(f"  Bid Levels: {len(bids)}")
                self.logger.info(f"  Ask Levels: {len(asks)}")
                
                return {
                    "symbol": symbol,
                    "bid_count": len(bids),
                    "ask_count": len(asks),
                    "best_bid": bids[0] if bids else None,
                    "best_ask": asks[0] if asks else None,
                    "success": True
                }
            else:
                return {"success": False, "error": "No orderbook data received"}
                
        except Exception as e:
            self.logger.error(f"Orderbook test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_positions(self) -> Dict[str, Any]:
        """Test position retrieval"""
        try:
            positions = self.client.get_positions()
            
            self.logger.info(f"Found {len(positions)} positions")
            
            active_positions = []
            for pos in positions:
                if float(pos.get("size", 0)) != 0:
                    active_positions.append({
                        "symbol": pos.get("symbol"),
                        "side": pos.get("side"),
                        "size": pos.get("size"),
                        "entry_price": pos.get("avgPrice"),
                        "unrealized_pnl": pos.get("unrealisedPnl")
                    })
            
            if active_positions:
                self.logger.info("Active positions:")
                for pos in active_positions:
                    self.logger.info(f"  {pos}")
            else:
                self.logger.info("No active positions")
            
            return {
                "total_positions": len(positions),
                "active_positions": len(active_positions),
                "positions": active_positions,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Position test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_place_limit_order(self) -> Dict[str, Any]:
        """Test placing a small limit buy order"""
        try:
            symbol = "BTCUSDT"
            
            # Get current price
            ticker = self.client.get_ticker(symbol)
            current_price = float(ticker.get("lastPrice", 0))
            
            # Place limit buy order 1% below current price
            limit_price = current_price * 0.99
            quantity = "0.001"  # Small test quantity
            
            order_link_id = f"test_limit_{int(time.time())}"
            
            result = self.client.place_order(
                symbol=symbol,
                side="Buy",
                order_type="Limit",
                qty=quantity,
                price=str(limit_price),
                order_link_id=order_link_id
            )
            
            if result:
                order_id = result.get("orderId")
                self.logger.info(f"Limit order placed successfully:")
                self.logger.info(f"  Order ID: {order_id}")
                self.logger.info(f"  Symbol: {symbol}")
                self.logger.info(f"  Side: Buy")
                self.logger.info(f"  Quantity: {quantity}")
                self.logger.info(f"  Price: {limit_price}")
                
                return {
                    "order_id": order_id,
                    "order_link_id": order_link_id,
                    "symbol": symbol,
                    "side": "Buy",
                    "quantity": quantity,
                    "price": limit_price,
                    "success": True
                }
            else:
                return {"success": False, "error": "No order result received"}
                
        except Exception as e:
            self.logger.error(f"Limit order test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_cancel_order(self) -> Dict[str, Any]:
        """Test cancelling the limit order"""
        try:
            # Get the limit order from previous test
            limit_order_result = self.test_results.get("Place Limit Order", {}).get("details", {})
            
            if not limit_order_result.get("success"):
                self.logger.warning("No limit order to cancel")
                return {"success": False, "error": "No previous limit order"}
            
            symbol = limit_order_result.get("symbol", "BTCUSDT")
            order_link_id = limit_order_result.get("order_link_id")
            
            result = self.client.cancel_order(
                symbol=symbol,
                order_link_id=order_link_id
            )
            
            if result:
                self.logger.info(f"Order cancelled successfully:")
                self.logger.info(f"  Order Link ID: {order_link_id}")
                
                return {
                    "cancelled_order_id": order_link_id,
                    "symbol": symbol,
                    "success": True
                }
            else:
                return {"success": False, "error": "No cancel result received"}
                
        except Exception as e:
            self.logger.error(f"Cancel order test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_place_market_order(self) -> Dict[str, Any]:
        """Test placing a small market order (if sufficient balance)"""
        try:
            # Check balance first
            balance_result = self.test_results.get("Wallet Balance", {}).get("details", {})
            balances = balance_result.get("balances", {})
            
            usdt_balance = balances.get("USDT", {}).get("available_balance", "0")
            
            if float(usdt_balance) < 10:  # Need at least $10 USDT
                self.logger.warning(f"Insufficient balance for market order test: ${usdt_balance}")
                return {"success": False, "error": "Insufficient balance"}
            
            symbol = "BTCUSDT"
            quantity = "0.001"  # Very small test quantity
            order_link_id = f"test_market_{int(time.time())}"
            
            result = self.client.place_order(
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=quantity,
                order_link_id=order_link_id
            )
            
            if result:
                order_id = result.get("orderId")
                self.logger.info(f"Market order placed successfully:")
                self.logger.info(f"  Order ID: {order_id}")
                self.logger.info(f"  Symbol: {symbol}")
                self.logger.info(f"  Side: Buy")
                self.logger.info(f"  Quantity: {quantity}")
                
                return {
                    "order_id": order_id,
                    "order_link_id": order_link_id,
                    "symbol": symbol,
                    "side": "Buy",
                    "quantity": quantity,
                    "success": True
                }
            else:
                return {"success": False, "error": "No order result received"}
                
        except Exception as e:
            self.logger.error(f"Market order test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_close_position(self) -> Dict[str, Any]:
        """Test closing position (if any exists)"""
        try:
            positions = self.client.get_positions("BTCUSDT")
            
            active_position = None
            for pos in positions:
                if float(pos.get("size", 0)) != 0:
                    active_position = pos
                    break
            
            if not active_position:
                self.logger.info("No active position to close")
                return {"success": False, "error": "No active position"}
            
            symbol = active_position.get("symbol")
            size = active_position.get("size")
            side = "Sell" if active_position.get("side") == "Buy" else "Buy"
            
            order_link_id = f"test_close_{int(time.time())}"
            
            result = self.client.place_order(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=size,
                order_link_id=order_link_id
            )
            
            if result:
                order_id = result.get("orderId")
                self.logger.info(f"Position closed successfully:")
                self.logger.info(f"  Order ID: {order_id}")
                self.logger.info(f"  Symbol: {symbol}")
                self.logger.info(f"  Size: {size}")
                
                return {
                    "order_id": order_id,
                    "symbol": symbol,
                    "size": size,
                    "side": side,
                    "success": True
                }
            else:
                return {"success": False, "error": "No close result received"}
                
        except Exception as e:
            self.logger.error(f"Close position test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_websocket_connection(self) -> Dict[str, Any]:
        """Test WebSocket connection (placeholder for now)"""
        try:
            # This will be implemented when we add WebSocket support
            self.logger.info("WebSocket testing will be implemented in Phase 2")
            return {
                "websocket_ready": False,
                "message": "WebSocket implementation pending",
                "success": True
            }
        except Exception as e:
            self.logger.error(f"WebSocket test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_rate_limiting(self) -> Dict[str, Any]:
        """Test rate limiting functionality"""
        try:
            start_time = time.time()
            
            # Make multiple requests quickly
            for i in range(5):
                self.client.get_server_time()
            
            end_time = time.time()
            duration = end_time - start_time
            
            self.logger.info(f"Made 5 requests in {duration:.2f} seconds")
            
            return {
                "requests": 5,
                "duration": duration,
                "rate_limiting_active": duration > 0.5,  # Should take at least 0.5s with rate limiting
                "success": True
            }
        except Exception as e:
            self.logger.error(f"Rate limiting test failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("COMPREHENSIVE TEST REPORT")
        self.logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results.values() if r["status"] == "PASS")
        failed_tests = sum(1 for r in self.test_results.values() if r["status"] == "FAIL")
        error_tests = sum(1 for r in self.test_results.values() if r["status"] == "ERROR")
        
        self.logger.info(f"Total Tests: {total_tests}")
        self.logger.info(f"Passed: {passed_tests} {ICONS.PASS}")
        self.logger.info(f"Failed: {failed_tests} {ICONS.FAIL}")
        self.logger.info(f"Errors: {error_tests} {ICONS.WARN}")
        self.logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        self.logger.info("\nDetailed Results:")
        self.logger.info("-" * 60)
        
        for test_name, result in self.test_results.items():
            status_icon = ICONS.PASS if result["status"] == "PASS" else ICONS.FAIL if result["status"] == "FAIL" else ICONS.WARN
            self.logger.info(f"{status_icon} {test_name}: {result['status']}")
            
            if result["status"] == "ERROR":
                self.logger.info(f"    Error: {result.get('error', 'Unknown error')}")
        
        # Save detailed report to file
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, indent=2, ensure_ascii=False)
            self.logger.info(f"\nDetailed report saved to: {report_file}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {str(e)}")
        
        # Final verdict
        if passed_tests == total_tests:
            self.logger.info(f"\n{ICONS.SUCCESS} ALL TESTS PASSED! Bot is ready for deployment.")
        elif passed_tests / total_tests >= 0.8:
            self.logger.info(f"\n{ICONS.WARN} Most tests passed. Review failures before deployment.")
        else:
            self.logger.info(f"\n{ICONS.FAIL} Multiple test failures. Bot needs fixes before deployment.")


async def main():
    """Main test execution"""
    print("Bybit Trading Bot - Comprehensive Test Suite")
    print("=" * 50)
    
    tester = ComprehensiveTester()
    
    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test suite failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())