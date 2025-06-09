#!/usr/bin/env python3
"""
PyBit Bot - Main entry point

This script initializes and runs the PyBit Bot trading system:

1. Loads API credentials from .env file
2. Loads configuration from config.json 
3. Initializes the Bybit client with proper authentication
4. Sets up the Data Manager to handle market data
5. Sets up the Order Manager for trade execution and position tracking
6. Downloads historical data for configured timeframes
7. Establishes WebSocket connection for real-time updates
8. Synchronizes with server time for precise candle tracking
9. Provides order execution capabilities with proper risk management
10. Maintains accurate position and order state
11. Implements clean shutdown mechanism

Phase 3 implementation focuses on order management, including USDT-based
position sizing, order execution, position tracking, and synchronization
with the exchange.
"""

import os
import sys
import time
import signal
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from pybit_bot import (
    BybitClient, 
    Logger, 
    ConfigLoader, 
    load_credentials,
    BybitAPIError,
    ConfigurationError
)
from pybit_bot.managers.data_manager import DataManager
from pybit_bot.managers.order_manager import OrderManager, OrderSide, OrderType, OrderStatus


class PyBitBot:
    """
    Main bot class coordinating all functionality
    """
    
    def __init__(self):
        # Initialize logger
        self.logger = Logger("PyBitBot", log_to_file=True)
        self.logger.info("=" * 60)
        self.logger.info(f"PyBit Bot starting - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 60)
        
        # Load configuration
        try:
            self.config = ConfigLoader(logger=self.logger)
            self.logger.info("Configuration loaded successfully")
        except ConfigurationError as e:
            self.logger.error(f"Configuration error: {e}")
            sys.exit(1)
        
        # Set log level from config
        log_level = self.config.get("system.log_level", "INFO")
        self.logger.set_level(log_level)
        self.logger.info(f"Log level set to {log_level}")
        
        # Initialize client
        try:
            credentials = load_credentials(logger=self.logger)
            self.client = BybitClient(credentials, self.logger)
            self.logger.info("Bybit client initialized")
        except (ConfigurationError, BybitAPIError) as e:
            self.logger.error(f"Client initialization error: {e}")
            sys.exit(1)
        
        # Initialize data manager with candle callback
        self.data_manager = DataManager(
            client=self.client,
            config=self.config,
            logger=self.logger,
            on_candle_close=self.on_candle_close
        )
        self.logger.info("Data manager initialized")
        
        # Initialize order manager
        self.order_manager = OrderManager(
            client=self.client,
            config=self.config,
            logger=self.logger
        )
        self.logger.info("Order manager initialized")
        
        # Trading symbol
        self.symbol = self.config.get("trading.symbol", "BTCUSDT")
        
        # Handle graceful shutdown
        self._setup_signal_handlers()
        
        # Flag to track if the bot is running
        self.running = False
        
        # Demo mode for testing
        self.demo_mode = False
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received shutdown signal {signum}")
        self.running = False
        self.logger.info("Shutting down gracefully...")
    
    def on_candle_close(self, timeframe: str, candle_data):
        """
        Callback for when a new candle closes
        
        Args:
            timeframe: The timeframe of the closed candle
            candle_data: Pandas Series with candle OHLCV data
        """
        timestamp = candle_data['timestamp']
        dt_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp)
        
        self.logger.info(f"CANDLE CLOSED - {timeframe} at {dt_str}")
        self.logger.info(f"  OHLC: {candle_data['open']:.2f} | {candle_data['high']:.2f} | {candle_data['low']:.2f} | {candle_data['close']:.2f}")
        self.logger.info(f"  Volume: {candle_data['volume']:.2f}")
        
        # In demo mode, place a test order on 1m candle close
        if self.demo_mode and timeframe == "1m" and self.running:
            asyncio.create_task(self._place_demo_order(candle_data))
    
    async def _place_demo_order(self, candle_data):
        """Place a demo order for testing"""
        # Only place a demo order if we don't have any positions
        position = self.order_manager.get_position(self.symbol)
        
        if position and position.is_active():
            self.logger.info("Already have an active position, skipping demo order")
            return
        
        # Randomly choose between buy and sell
        import random
        side = OrderSide.BUY if random.random() > 0.5 else OrderSide.SELL
        
        # Use a small position size for testing
        usdt_amount = self.config.get("trading.position_size_usdt", 50.0) / 10.0
        
        self.logger.info(f"Placing demo {side.value} order for {usdt_amount} USDT")
        
        # Place a market order with take profit and stop loss
        order = await self.order_manager.place_market_order(
            side=side,
            usdt_amount=usdt_amount,
            tp_pct=self.config.get("risk.take_profit_pct", 0.04),
            sl_pct=self.config.get("risk.stop_loss_pct", 0.02)
        )
        
        if order:
            self.logger.info(f"Demo order placed successfully: {order.order_id}")
            
            # Schedule order cancellation in 5 minutes if not filled
            async def cancel_after_delay():
                await asyncio.sleep(300)  # 5 minutes
                status = self.order_manager.get_order_status(order.order_link_id)
                if status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
                    self.logger.info(f"Canceling unfilled demo order: {order.order_link_id}")
                    await self.order_manager.cancel_order(order.order_link_id)
                    
            asyncio.create_task(cancel_after_delay())
        else:
            self.logger.error("Failed to place demo order")
    
    async def start(self):
        """Start the bot"""
        self.logger.info("Starting PyBit Bot...")
        
        # Test connection
        if not self.client.test_connection():
            self.logger.error("Failed to connect to Bybit API")
            return False
        
        self.logger.info("Connection to Bybit API successful")
        
        # Get server time to check connection
        try:
            server_time = self.client.get_server_time()
            time_str = datetime.fromtimestamp(int(server_time.get("timeSecond", 0)))
            self.logger.info(f"Bybit server time: {time_str}")
        except BybitAPIError as e:
            self.logger.error(f"Failed to get server time: {e}")
        
        # Get account balance
        try:
            balance = self.client.get_wallet_balance()
            if balance.get("list"):
                account = balance["list"][0]
                self.logger.info(f"Account type: {account.get('accountType')}")
                self.logger.info(f"Total equity: {account.get('totalEquity')}")
                
                for coin in account.get("coin", []):
                    if float(coin.get("walletBalance", 0)) > 0:
                        self.logger.info(f"{coin.get('coin')} balance: {coin.get('walletBalance')}")
        except BybitAPIError as e:
            self.logger.error(f"Failed to get wallet balance: {e}")
        
        # Initialize data manager
        try:
            self.logger.info("Initializing data manager...")
            await self.data_manager.initialize()
        except Exception as e:
            self.logger.error(f"Failed to initialize data manager: {e}")
            return False
        
        # Initialize order manager
        try:
            self.logger.info("Initializing order manager...")
            await self.order_manager.initialize()
        except Exception as e:
            self.logger.error(f"Failed to initialize order manager: {e}")
            return False
        
        return True
    
    async def run(self):
        """Run the main bot loop"""
        # Start the bot
        if not await self.start():
            return
        
        self.running = True
        
        # Main run loop
        try:
            self.logger.info("Bot running... Press Ctrl+C to stop")
            
            # Display initial data summary
            await self._display_data_summary()
            
            # Display initial order and position summary
            await self._display_order_summary()
            
            # Main timeframe
            main_tf = self.config.get("trading.timeframe", "1m")
            
            # Update interval (in seconds)
            update_interval = self.config.get("data.update_interval", 60)
            
            # Keep running until shutdown signal
            while self.running:
                # Get current server time
                server_time = self.data_manager.get_server_time()
                server_datetime = datetime.fromtimestamp(server_time)
                
                # Get next candle time
                next_candle_time = self.data_manager.get_next_candle_time(main_tf)
                next_candle_datetime = datetime.fromtimestamp(next_candle_time)
                
                # Calculate time until next candle
                time_until_next = next_candle_time - server_time
                
                # Display timing information
                self.logger.info(f"Current server time: {server_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"Next {main_tf} candle closes: {next_candle_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"Time until next candle: {time_until_next:.2f} seconds")
                
                # Update order manager
                await self.order_manager.update()
                
                # Display order and position summary
                await self._display_order_summary()
                
                # Wait until next update
                await asyncio.sleep(min(update_interval, time_until_next))
                
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            # Cleanup
            await self._shutdown()
            
    async def _display_data_summary(self):
        """Display summary of available data"""
        symbol = self.config.get("trading.symbol", "BTCUSDT")
        current_price = self.data_manager.get_latest_price()
        
        self.logger.info(f"Current {symbol} price: {current_price}")
        
        for timeframe in self.data_manager.lookback_bars.keys():
            df = self.data_manager.get_data(timeframe)
            if not df.empty:
                self.logger.info(f"{timeframe} data: {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    
    async def _display_order_summary(self):
        """Display summary of orders and positions"""
        # Active positions
        active_positions = self.order_manager.get_active_position_count()
        self.logger.info(f"Active positions: {active_positions}")
        
        # Show position details if any
        for symbol, position in self.order_manager.positions.items():
            if position.is_active():
                side_str = "LONG" if position.side.name == "LONG" else "SHORT"
                pnl = position.unrealized_pnl
                pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
                self.logger.info(f"  {symbol} {side_str}: {position.size} @ {position.entry_price:.2f} (PnL: {pnl_str} USDT)")
                
                if position.take_profit:
                    self.logger.info(f"    Take profit: {position.take_profit:.2f}")
                if position.stop_loss:
                    self.logger.info(f"    Stop loss: {position.stop_loss:.2f}")
        
        # Active orders
        active_orders = self.order_manager.get_active_order_count()
        self.logger.info(f"Active orders: {active_orders}")
        
        # Show order details if any
        for order_id, order in self.order_manager.orders.items():
            if order.status.name in ["SUBMITTED", "PARTIALLY_FILLED"]:
                price_str = f"@ {order.price:.2f}" if order.price else "MARKET"
                self.logger.info(f"  {order.side.name} {order.qty} {order.symbol} {price_str} ({order.status.name})")
        
        # Daily PnL
        daily_pnl = self.order_manager.get_daily_pnl()
        daily_pnl_str = f"+{daily_pnl:.2f}" if daily_pnl >= 0 else f"{daily_pnl:.2f}"
        self.logger.info(f"Daily PnL: {daily_pnl_str} USDT")
    
    async def place_test_order(self, side, market=True):
        """Place a test order"""
        try:
            self.logger.info(f"Placing test {side} {'market' if market else 'limit'} order")
            
            position_size_usdt = self.config.get("trading.position_size_usdt", 50.0) / 10.0  # Use 1/10th for testing
            current_price = self.data_manager.get_latest_price()
            
            if market:
                # Place market order
                order = await self.order_manager.place_market_order(
                    side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
                    usdt_amount=position_size_usdt,
                    tp_pct=self.config.get("risk.take_profit_pct", 0.04),
                    sl_pct=self.config.get("risk.stop_loss_pct", 0.02)
                )
            else:
                # Place limit order
                # For buy, use a price slightly below market
                # For sell, use a price slightly above market
                if side.upper() == "BUY":
                    price = current_price * 0.995  # 0.5% below market
                else:
                    price = current_price * 1.005  # 0.5% above market
                
                order = await self.order_manager.place_limit_order(
                    side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
                    price=price,
                    usdt_amount=position_size_usdt,
                    tp_pct=self.config.get("risk.take_profit_pct", 0.04),
                    sl_pct=self.config.get("risk.stop_loss_pct", 0.02)
                )
            
            if order:
                self.logger.info(f"Test order placed successfully: {order.order_id}")
                return True
            else:
                self.logger.error("Failed to place test order")
                return False
                
        except Exception as e:
            self.logger.error(f"Error placing test order: {e}")
            return False
    
    async def cancel_all_test_orders(self):
        """Cancel all test orders"""
        try:
            self.logger.info("Canceling all orders")
            result = await self.order_manager.cancel_all_orders()
            if result:
                self.logger.info("All orders canceled successfully")
            else:
                self.logger.error("Failed to cancel all orders")
            return result
        except Exception as e:
            self.logger.error(f"Error canceling orders: {e}")
            return False
    
    async def close_all_test_positions(self):
        """Close all test positions"""
        try:
            self.logger.info("Closing all positions")
            result = await self.order_manager.close_all_positions()
            if result:
                self.logger.info("All positions closed successfully")
            else:
                self.logger.error("Failed to close all positions")
            return result
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
            return False
    
    async def _shutdown(self):
        """Perform graceful shutdown"""
        self.logger.info("Performing graceful shutdown...")
        
        # Cancel all open orders if requested
        if input("Cancel all open orders? (y/n): ").lower() == 'y':
            await self.order_manager.cancel_all_orders()
        
        # Close all positions if requested
        if input("Close all positions? (y/n): ").lower() == 'y':
            await self.order_manager.close_all_positions()
        
        # Close data manager connections
        try:
            await self.data_manager.close()
        except Exception as e:
            self.logger.error(f"Error closing data manager: {e}")
        
        self.logger.info("Bot shutdown complete")


async def main():
    """Main function"""
    bot = PyBitBot()
    
    # Interactive mode for testing
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        await bot.start()
        
        while True:
            print("\nPyBit Bot Interactive Mode")
            print("1. Run bot normally")
            print("2. Place test BUY market order")
            print("3. Place test SELL market order")
            print("4. Place test BUY limit order")
            print("5. Place test SELL limit order")
            print("6. Cancel all orders")
            print("7. Close all positions")
            print("8. Toggle demo mode")
            print("9. Exit")
            
            choice = input("Enter choice: ")
            
            if choice == "1":
                await bot.run()
            elif choice == "2":
                await bot.place_test_order("BUY", market=True)
            elif choice == "3":
                await bot.place_test_order("SELL", market=True)
            elif choice == "4":
                await bot.place_test_order("BUY", market=False)
            elif choice == "5":
                await bot.place_test_order("SELL", market=False)
            elif choice == "6":
                await bot.cancel_all_test_orders()
            elif choice == "7":
                await bot.close_all_test_positions()
            elif choice == "8":
                bot.demo_mode = not bot.demo_mode
                print(f"Demo mode is now {'ON' if bot.demo_mode else 'OFF'}")
            elif choice == "9":
                print("Exiting...")
                break
            else:
                print("Invalid choice")
    else:
        # Run normally
        await bot.run()


if __name__ == "__main__":
    asyncio.run(main())