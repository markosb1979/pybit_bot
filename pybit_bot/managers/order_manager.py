"""
Order Manager for PyBit Bot

This module is responsible for:
1. Converting USDT position sizes to contract quantities
2. Submitting, tracking, and canceling orders
3. Managing position state and synchronization with exchange
4. Handling order execution and fill events
5. Implementing proper error handling for order operations
6. Maintaining accurate records of all trading activity
7. Providing order-related metrics and status information

The OrderManager serves as the central component for all trading operations,
ensuring reliable order execution and accurate position tracking.
"""

import time
import uuid
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pandas as pd
from dataclasses import dataclass, field
from enum import Enum

from ..core.client import BybitClient
from ..utils.logger import Logger
from ..utils.config_loader import ConfigLoader
from ..exceptions.errors import (
    InvalidOrderError, InsufficientBalanceError, OrderExecutionError
)


class OrderSide(str, Enum):
    """Order side enum"""
    BUY = "Buy"
    SELL = "Sell"


class OrderType(str, Enum):
    """Order type enum"""
    MARKET = "Market"
    LIMIT = "Limit"
    STOP = "Stop"
    STOP_MARKET = "StopMarket"
    TAKE_PROFIT = "TakeProfit"
    TAKE_PROFIT_MARKET = "TakeProfitMarket"


class OrderStatus(str, Enum):
    """Order status enum"""
    CREATED = "Created"          # Local state - order created but not sent
    SUBMITTED = "New"            # Order sent to exchange but not filled
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELED = "Cancelled"
    REJECTED = "Rejected"
    FAILED = "FAILED"            # Local state - failed to submit


class PositionSide(str, Enum):
    """Position side enum"""
    LONG = "Long"
    SHORT = "Short"
    NONE = "None"


@dataclass
class Order:
    """Order data structure"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float
    price: Optional[float] = None
    order_link_id: str = field(default_factory=lambda: f"pybit_{uuid.uuid4().hex[:8]}")
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.CREATED
    create_time: float = field(default_factory=time.time)
    update_time: float = field(default_factory=time.time)
    filled_qty: float = 0.0
    avg_price: Optional[float] = None
    trigger_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    time_in_force: str = "GTC"
    reduce_only: bool = False
    close_on_trigger: bool = False
    position_idx: int = 0  # 0 for one-way, 1 for buy, 2 for sell
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API submission"""
        order_dict = {
            "category": "linear",
            "symbol": self.symbol,
            "side": self.side.value,
            "orderType": self.order_type.value,
            "qty": str(self.qty),
            "timeInForce": self.time_in_force,
            "orderLinkId": self.order_link_id,
            "reduceOnly": self.reduce_only,
            "closeOnTrigger": self.close_on_trigger,
        }
        
        # Add conditional fields
        if self.price is not None:
            order_dict["price"] = str(self.price)
        
        if self.trigger_price is not None:
            order_dict["triggerPrice"] = str(self.trigger_price)
            
        if self.stop_loss is not None:
            order_dict["stopLoss"] = str(self.stop_loss)
            
        if self.take_profit is not None:
            order_dict["takeProfit"] = str(self.take_profit)
            
        return order_dict
    
    def update_from_response(self, response: Dict[str, Any]) -> None:
        """Update order details from API response"""
        if "orderId" in response:
            self.order_id = response["orderId"]
            
        if "orderStatus" in response:
            try:
                self.status = OrderStatus(response["orderStatus"])
            except ValueError:
                # If status is not in our enum, use SUBMITTED as default
                self.status = OrderStatus.SUBMITTED
                
        if "cumExecQty" in response:
            self.filled_qty = float(response["cumExecQty"])
            
        if "avgPrice" in response and response["avgPrice"]:
            self.avg_price = float(response["avgPrice"])
            
        self.update_time = time.time()


@dataclass
class Position:
    """Position data structure"""
    symbol: str
    side: PositionSide = PositionSide.NONE
    size: float = 0.0
    entry_price: Optional[float] = None
    liquidation_price: Optional[float] = None
    bankruptcy_price: Optional[float] = None
    margin: Optional[float] = None
    leverage: float = 1.0
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    create_time: float = field(default_factory=time.time)
    update_time: float = field(default_factory=time.time)
    
    def update_from_response(self, response: Dict[str, Any]) -> None:
        """Update position details from API response"""
        if "side" in response:
            if response["side"] == "Buy":
                self.side = PositionSide.LONG
            elif response["side"] == "Sell":
                self.side = PositionSide.SHORT
            else:
                self.side = PositionSide.NONE
                
        if "size" in response:
            self.size = float(response["size"])
            
        if "entryPrice" in response and response["entryPrice"]:
            self.entry_price = float(response["entryPrice"])
            
        if "liqPrice" in response and response["liqPrice"]:
            self.liquidation_price = float(response["liqPrice"])
            
        if "bustPrice" in response and response["bustPrice"]:
            self.bankruptcy_price = float(response["bustPrice"])
            
        if "positionIM" in response:
            self.margin = float(response["positionIM"])
            
        if "leverage" in response:
            self.leverage = float(response["leverage"])
            
        if "takeProfit" in response and response["takeProfit"]:
            self.take_profit = float(response["takeProfit"])
            
        if "stopLoss" in response and response["stopLoss"]:
            self.stop_loss = float(response["stopLoss"])
            
        if "unrealisedPnl" in response:
            self.unrealized_pnl = float(response["unrealisedPnl"])
            
        if "cumRealisedPnl" in response:
            self.realized_pnl = float(response["cumRealisedPnl"])
            
        self.update_time = time.time()
    
    def is_active(self) -> bool:
        """Check if position is active"""
        return self.side != PositionSide.NONE and self.size > 0
    
    def get_direction_multiplier(self) -> int:
        """Get direction multiplier (1 for long, -1 for short, 0 for none)"""
        if self.side == PositionSide.LONG:
            return 1
        elif self.side == PositionSide.SHORT:
            return -1
        return 0
    
    def get_notional_value(self) -> float:
        """Get notional value of position"""
        if self.entry_price is None or self.size == 0:
            return 0.0
        return self.entry_price * self.size


class OrderManager:
    """
    Manages order submission, tracking, and position management
    """
    
    def __init__(
        self,
        client: BybitClient,
        config: ConfigLoader,
        logger: Optional[Logger] = None
    ):
        self.client = client
        self.config = config
        self.logger = logger or Logger("OrderManager")
        
        # Get trading symbol from config
        self.symbol = self.config.get("trading.symbol", "BTCUSDT")
        
        # Position size in USDT
        self.position_size_usdt = self.config.get("trading.position_size_usdt", 50.0)
        
        # Max positions
        self.max_positions = self.config.get("trading.max_positions", 3)
        
        # Risk settings
        self.stop_loss_pct = self.config.get("risk.stop_loss_pct", 0.02)
        self.take_profit_pct = self.config.get("risk.take_profit_pct", 0.04)
        self.max_daily_loss_usdt = self.config.get("risk.max_daily_loss_usdt", 100.0)
        
        # Order tracking
        self.orders: Dict[str, Order] = {}  # order_link_id -> Order
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        
        # Track filled orders for the day (for daily loss calculation)
        self.today_filled_orders: List[Order] = []
        self.today_realized_pnl = 0.0
        self.today_date = datetime.now().date()
        
        # Symbol precision info
        self.price_precision: Dict[str, int] = {}
        self.qty_precision: Dict[str, int] = {}
        
        # Initialization flag
        self.initialized = False
        
    async def initialize(self):
        """Initialize order manager"""
        self.logger.info(f"Initializing OrderManager for {self.symbol}")
        
        # Get instrument info for precision
        await self._fetch_instrument_info()
        
        # Synchronize positions with exchange
        await self.sync_positions()
        
        # Synchronize open orders with exchange
        await self.sync_open_orders()
        
        # Reset daily tracking if it's a new day
        current_date = datetime.now().date()
        if current_date != self.today_date:
            self.today_date = current_date
            self.today_filled_orders = []
            self.today_realized_pnl = 0.0
        
        self.initialized = True
        self.logger.info("OrderManager initialization completed")
        
        return True
        
    async def _fetch_instrument_info(self):
        """Fetch instrument info for precision settings"""
        try:
            # Call instruments API to get precision info
            params = {
                "category": "linear",
                "symbol": self.symbol
            }
            
            response = self.client._make_request(
                method="GET",
                endpoint="/v5/market/instruments-info",
                params=params,
                auth_required=False
            )
            
            instruments = response.get("list", [])
            if not instruments:
                self.logger.warning(f"No instrument info found for {self.symbol}")
                # Use defaults
                self.price_precision[self.symbol] = 2
                self.qty_precision[self.symbol] = 3
                return
            
            # Extract precision info
            instrument = instruments[0]
            
            # Determine price precision from tick size
            # For example, if tickSize is "0.01", precision is 2
            tick_size = float(instrument.get("priceFilter", {}).get("tickSize", "0.01"))
            self.price_precision[self.symbol] = self._get_precision_from_float(tick_size)
            
            # Determine quantity precision from lot size
            # For example, if lotSize is "0.001", precision is 3
            lot_size = float(instrument.get("lotSizeFilter", {}).get("qtyStep", "0.001"))
            self.qty_precision[self.symbol] = self._get_precision_from_float(lot_size)
            
            self.logger.info(f"Instrument precision - Price: {self.price_precision[self.symbol]} decimals, Quantity: {self.qty_precision[self.symbol]} decimals")
            
        except Exception as e:
            self.logger.error(f"Error fetching instrument info: {e}")
            # Use defaults
            self.price_precision[self.symbol] = 2
            self.qty_precision[self.symbol] = 3
    
    def _get_precision_from_float(self, value: float) -> int:
        """Get decimal precision from float value (e.g., 0.01 -> 2)"""
        str_value = str(value)
        if "e" in str_value:
            # Handle scientific notation
            return abs(int(str_value.split("e")[1]))
        elif "." in str_value:
            # Count decimals
            return len(str_value.split(".")[1].rstrip("0"))
        return 0
    
    async def sync_positions(self):
        """Synchronize positions with exchange"""
        try:
            positions = self.client.get_positions(self.symbol)
            
            # Update positions dictionary
            for pos_data in positions:
                symbol = pos_data.get("symbol")
                
                # Skip if no symbol or size is 0
                if not symbol or float(pos_data.get("size", "0")) == 0:
                    continue
                
                # Create or update position
                if symbol in self.positions:
                    position = self.positions[symbol]
                else:
                    position = Position(symbol=symbol)
                    self.positions[symbol] = position
                
                # Update position details
                position.update_from_response(pos_data)
                
                # Log position details
                if position.is_active():
                    side_str = "LONG" if position.side == PositionSide.LONG else "SHORT"
                    self.logger.info(f"Active {side_str} position: {position.size} {symbol} @ {position.entry_price}")
                    self.logger.info(f"Unrealized PnL: {position.unrealized_pnl} USDT")
            
            # Log if no active positions
            if not any(pos.is_active() for pos in self.positions.values()):
                self.logger.info("No active positions")
                
            return True
                
        except Exception as e:
            self.logger.error(f"Error syncing positions: {e}")
            return False
    
    async def sync_open_orders(self):
        """Synchronize open orders with exchange"""
        try:
            open_orders = self.client.get_open_orders(self.symbol)
            
            # Track orders that exist on exchange
            exchange_order_ids = set()
            
            # Update orders dictionary
            for order_data in open_orders:
                order_id = order_data.get("orderId")
                order_link_id = order_data.get("orderLinkId")
                
                # Skip if no order ID
                if not order_id:
                    continue
                
                exchange_order_ids.add(order_id)
                
                # Find order by order_link_id or create a new one
                order = None
                if order_link_id and order_link_id in self.orders:
                    order = self.orders[order_link_id]
                else:
                    # Create new order
                    order = Order(
                        symbol=order_data.get("symbol"),
                        side=OrderSide.BUY if order_data.get("side") == "Buy" else OrderSide.SELL,
                        order_type=OrderType(order_data.get("orderType")),
                        qty=float(order_data.get("qty", "0")),
                        price=float(order_data.get("price", "0")) if order_data.get("price") else None,
                        order_link_id=order_link_id or f"pybit_{uuid.uuid4().hex[:8]}",
                        order_id=order_id
                    )
                    self.orders[order.order_link_id] = order
                
                # Update order details
                order.update_from_response(order_data)
                
                # Log order details
                self.logger.info(f"Active order: {order.side.value} {order.qty} {order.symbol} @ {order.price or 'MARKET'}")
            
            # Remove orders that no longer exist on exchange
            orders_to_remove = []
            for order_link_id, order in self.orders.items():
                if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
                    if order.order_id and order.order_id not in exchange_order_ids:
                        # Order was filled or canceled on exchange but not updated locally
                        self.logger.warning(f"Order {order_link_id} not found on exchange, marking as CANCELED")
                        order.status = OrderStatus.CANCELED
                        orders_to_remove.append(order_link_id)
            
            # Remove canceled orders
            for order_link_id in orders_to_remove:
                del self.orders[order_link_id]
            
            # Log if no open orders
            if not any(order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED] for order in self.orders.values()):
                self.logger.info("No active orders")
                
            return True
                
        except Exception as e:
            self.logger.error(f"Error syncing open orders: {e}")
            return False
    
    def _round_price(self, price: float, symbol: str = None) -> float:
        """Round price to symbol precision"""
        symbol = symbol or self.symbol
        precision = self.price_precision.get(symbol, 2)
        return round(price, precision)
    
    def _round_quantity(self, qty: float, symbol: str = None) -> float:
        """Round quantity to symbol precision"""
        symbol = symbol or self.symbol
        precision = self.qty_precision.get(symbol, 3)
        return round(qty, precision)
    
    def calculate_quantity(self, price: float, usdt_amount: float = None, symbol: str = None) -> float:
        """
        Calculate order quantity based on USDT amount and current price
        
        Args:
            price: Current price
            usdt_amount: USDT amount to use (default: configured position size)
            symbol: Symbol to trade (default: configured symbol)
            
        Returns:
            Quantity rounded to symbol precision
        """
        symbol = symbol or self.symbol
        usdt_amount = usdt_amount or self.position_size_usdt
        
        # Calculate raw quantity
        raw_qty = usdt_amount / price
        
        # Round to symbol precision
        return self._round_quantity(raw_qty, symbol)
    
    def calculate_stop_loss(self, entry_price: float, side: OrderSide, pct: float = None) -> float:
        """
        Calculate stop loss price based on entry price and side
        
        Args:
            entry_price: Entry price
            side: Order side (BUY/SELL)
            pct: Stop loss percentage (default: configured stop_loss_pct)
            
        Returns:
            Stop loss price rounded to symbol precision
        """
        pct = pct or self.stop_loss_pct
        
        if side == OrderSide.BUY:
            # For long positions, stop loss is below entry
            stop_price = entry_price * (1 - pct)
        else:
            # For short positions, stop loss is above entry
            stop_price = entry_price * (1 + pct)
            
        return self._round_price(stop_price)
    
    def calculate_take_profit(self, entry_price: float, side: OrderSide, pct: float = None) -> float:
        """
        Calculate take profit price based on entry price and side
        
        Args:
            entry_price: Entry price
            side: Order side (BUY/SELL)
            pct: Take profit percentage (default: configured take_profit_pct)
            
        Returns:
            Take profit price rounded to symbol precision
        """
        pct = pct or self.take_profit_pct
        
        if side == OrderSide.BUY:
            # For long positions, take profit is above entry
            tp_price = entry_price * (1 + pct)
        else:
            # For short positions, take profit is below entry
            tp_price = entry_price * (1 - pct)
            
        return self._round_price(tp_price)
    
    async def place_market_order(
        self,
        side: OrderSide,
        usdt_amount: float = None,
        tp_pct: float = None,
        sl_pct: float = None,
        reduce_only: bool = False,
        symbol: str = None
    ) -> Optional[Order]:
        """
        Place a market order
        
        Args:
            side: Order side (BUY/SELL)
            usdt_amount: USDT amount (default: configured position size)
            tp_pct: Take profit percentage (default: configured take_profit_pct)
            sl_pct: Stop loss percentage (default: configured stop_loss_pct)
            reduce_only: Whether this order can only reduce position
            symbol: Symbol to trade (default: configured symbol)
            
        Returns:
            Order object if successful, None otherwise
        """
        symbol = symbol or self.symbol
        usdt_amount = usdt_amount or self.position_size_usdt
        
        try:
            # Check max positions
            if not reduce_only and len([p for p in self.positions.values() if p.is_active()]) >= self.max_positions:
                self.logger.error(f"Maximum positions ({self.max_positions}) already reached")
                return None
            
            # Check daily loss limit
            if self.today_realized_pnl <= -self.max_daily_loss_usdt:
                self.logger.error(f"Daily loss limit reached: {self.today_realized_pnl} USDT")
                return None
            
            # Get current price
            ticker = self.client.get_ticker(symbol)
            if side == OrderSide.BUY:
                # Use ask price for buy orders
                price = float(ticker.get("ask1Price", ticker.get("lastPrice", "0")))
            else:
                # Use bid price for sell orders
                price = float(ticker.get("bid1Price", ticker.get("lastPrice", "0")))
                
            if price <= 0:
                self.logger.error(f"Invalid price: {price}")
                return None
            
            # Calculate quantity
            qty = self.calculate_quantity(price, usdt_amount, symbol)
            
            if qty <= 0:
                self.logger.error(f"Invalid quantity: {qty}")
                return None
            
            # Calculate TP/SL if specified
            take_profit = None
            stop_loss = None
            
            if tp_pct:
                take_profit = self.calculate_take_profit(price, side, tp_pct)
                
            if sl_pct:
                stop_loss = self.calculate_stop_loss(price, side, sl_pct)
            
            # Create order object
            order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET,
                qty=qty,
                price=None,  # Market order has no price
                take_profit=take_profit,
                stop_loss=stop_loss,
                reduce_only=reduce_only
            )
            
            # Log order details
            self.logger.info(f"Placing {side.value} MARKET order: {qty} {symbol} (~{usdt_amount} USDT)")
            if take_profit:
                self.logger.info(f"Take profit: {take_profit}")
            if stop_loss:
                self.logger.info(f"Stop loss: {stop_loss}")
            
            # Submit order to exchange
            response = self.client.place_order(
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                qty=str(order.qty),
                time_in_force=order.time_in_force,
                order_link_id=order.order_link_id,
                stop_loss=str(order.stop_loss) if order.stop_loss else None,
                take_profit=str(order.take_profit) if order.take_profit else None,
                reduce_only=order.reduce_only
            )
            
            # Update order from response
            if "orderId" in response:
                order.order_id = response["orderId"]
                order.status = OrderStatus.SUBMITTED
                
                # Add to orders dictionary
                self.orders[order.order_link_id] = order
                
                self.logger.info(f"Order placed successfully: {order.order_id}")
                
                # Query order status after a short delay to check if it was filled
                await asyncio.sleep(1)
                await self._update_order_status(order)
                
                return order
            else:
                self.logger.error(f"Failed to place order: {response}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error placing market order: {e}")
            return None
    
    async def place_limit_order(
        self,
        side: OrderSide,
        price: float,
        usdt_amount: float = None,
        tp_pct: float = None,
        sl_pct: float = None,
        reduce_only: bool = False,
        symbol: str = None
    ) -> Optional[Order]:
        """
        Place a limit order
        
        Args:
            side: Order side (BUY/SELL)
            price: Limit price
            usdt_amount: USDT amount (default: configured position size)
            tp_pct: Take profit percentage (default: configured take_profit_pct)
            sl_pct: Stop loss percentage (default: configured stop_loss_pct)
            reduce_only: Whether this order can only reduce position
            symbol: Symbol to trade (default: configured symbol)
            
        Returns:
            Order object if successful, None otherwise
        """
        symbol = symbol or self.symbol
        usdt_amount = usdt_amount or self.position_size_usdt
        
        try:
            # Check max positions
            if not reduce_only and len([p for p in self.positions.values() if p.is_active()]) >= self.max_positions:
                self.logger.error(f"Maximum positions ({self.max_positions}) already reached")
                return None
            
            # Check daily loss limit
            if self.today_realized_pnl <= -self.max_daily_loss_usdt:
                self.logger.error(f"Daily loss limit reached: {self.today_realized_pnl} USDT")
                return None
            
            # Round price to symbol precision
            price = self._round_price(price, symbol)
            
            # Calculate quantity
            qty = self.calculate_quantity(price, usdt_amount, symbol)
            
            if qty <= 0:
                self.logger.error(f"Invalid quantity: {qty}")
                return None
            
            # Calculate TP/SL if specified
            take_profit = None
            stop_loss = None
            
            if tp_pct:
                take_profit = self.calculate_take_profit(price, side, tp_pct)
                
            if sl_pct:
                stop_loss = self.calculate_stop_loss(price, side, sl_pct)
            
            # Create order object
            order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.LIMIT,
                qty=qty,
                price=price,
                take_profit=take_profit,
                stop_loss=stop_loss,
                reduce_only=reduce_only
            )
            
            # Log order details
            self.logger.info(f"Placing {side.value} LIMIT order: {qty} {symbol} @ {price} (~{usdt_amount} USDT)")
            if take_profit:
                self.logger.info(f"Take profit: {take_profit}")
            if stop_loss:
                self.logger.info(f"Stop loss: {stop_loss}")
            
            # Submit order to exchange
            response = self.client.place_order(
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                qty=str(order.qty),
                price=str(order.price),
                time_in_force=order.time_in_force,
                order_link_id=order.order_link_id,
                stop_loss=str(order.stop_loss) if order.stop_loss else None,
                take_profit=str(order.take_profit) if order.take_profit else None,
                reduce_only=order.reduce_only
            )
            
            # Update order from response
            if "orderId" in response:
                order.order_id = response["orderId"]
                order.status = OrderStatus.SUBMITTED
                
                # Add to orders dictionary
                self.orders[order.order_link_id] = order
                
                self.logger.info(f"Order placed successfully: {order.order_id}")
                return order
            else:
                self.logger.error(f"Failed to place order: {response}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error placing limit order: {e}")
            return None
    
    async def cancel_order(self, order_link_id: str) -> bool:
        """
        Cancel an order
        
        Args:
            order_link_id: Order link ID
            
        Returns:
            True if canceled successfully, False otherwise
        """
        if order_link_id not in self.orders:
            self.logger.error(f"Order {order_link_id} not found")
            return False
        
        order = self.orders[order_link_id]
        
        # Check if order can be canceled
        if order.status not in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
            self.logger.warning(f"Order {order_link_id} cannot be canceled (status: {order.status})")
            return False
        
        try:
            self.logger.info(f"Canceling order: {order_link_id}")
            
            # Cancel order on exchange
            response = self.client.cancel_order(
                symbol=order.symbol,
                order_link_id=order_link_id
            )
            
            if "orderId" in response:
                # Update order status
                order.status = OrderStatus.CANCELED
                order.update_time = time.time()
                
                self.logger.info(f"Order canceled successfully: {order_link_id}")
                return True
            else:
                self.logger.error(f"Failed to cancel order: {response}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error canceling order: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: str = None) -> bool:
        """
        Cancel all open orders
        
        Args:
            symbol: Symbol to cancel orders for (default: all symbols)
            
        Returns:
            True if canceled successfully, False otherwise
        """
        try:
            # Get open orders
            orders_to_cancel = []
            for order_link_id, order in self.orders.items():
                if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
                    if symbol is None or order.symbol == symbol:
                        orders_to_cancel.append(order_link_id)
            
            if not orders_to_cancel:
                self.logger.info("No orders to cancel")
                return True
            
            self.logger.info(f"Canceling {len(orders_to_cancel)} orders")
            
            # Cancel each order
            success = True
            for order_link_id in orders_to_cancel:
                if not await self.cancel_order(order_link_id):
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error canceling all orders: {e}")
            return False
    
    async def _update_order_status(self, order: Order) -> bool:
        """
        Update order status from exchange
        
        Args:
            order: Order to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # If order has no order_id, it was never submitted
            if not order.order_id:
                return False
            
            # Get order from exchange
            params = {
                "category": "linear",
                "symbol": order.symbol,
                "orderId": order.order_id
            }
            
            response = self.client._make_request(
                method="GET",
                endpoint="/v5/order/history",
                params=params
            )
            
            order_list = response.get("list", [])
            if not order_list:
                self.logger.warning(f"Order {order.order_id} not found on exchange")
                return False
            
            # Update order from response
            order_data = order_list[0]
            order.update_from_response(order_data)
            
            # If order is filled, update position and track for daily PnL
            if order.status == OrderStatus.FILLED and order.filled_qty > 0:
                # Update positions
                await self.sync_positions()
                
                # Add to today's filled orders
                self.today_filled_orders.append(order)
                
                # Calculate realized PnL if this was a closing order
                if order.reduce_only:
                    # Get the matching position
                    position = self.positions.get(order.symbol)
                    if position:
                        # Update realized PnL
                        self.today_realized_pnl += position.realized_pnl
                
                self.logger.info(f"Order {order.order_id} filled: {order.filled_qty} @ {order.avg_price}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating order status: {e}")
            return False
    
    async def update_all_orders(self) -> bool:
        """
        Update status for all orders
        
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Get orders that need updating
            orders_to_update = []
            for order in self.orders.values():
                if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
                    orders_to_update.append(order)
            
            if not orders_to_update:
                return True
            
            # Update each order
            success = True
            for order in orders_to_update:
                if not await self._update_order_status(order):
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error updating all orders: {e}")
            return False
    
    def get_position(self, symbol: str = None) -> Optional[Position]:
        """
        Get position for a symbol
        
        Args:
            symbol: Symbol to get position for (default: configured symbol)
            
        Returns:
            Position object if found, None otherwise
        """
        symbol = symbol or self.symbol
        return self.positions.get(symbol)
    
    async def close_position(self, symbol: str = None, market: bool = True) -> bool:
        """
        Close position for a symbol
        
        Args:
            symbol: Symbol to close position for (default: configured symbol)
            market: Whether to use market order (True) or limit order (False)
            
        Returns:
            True if closed successfully, False otherwise
        """
        symbol = symbol or self.symbol
        position = self.positions.get(symbol)
        
        if not position or not position.is_active():
            self.logger.warning(f"No active position for {symbol}")
            return False
        
        try:
            # Determine order side (opposite of position)
            side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
            
            # Get quantity to close
            qty = position.size
            
            if market:
                # Place market order to close position
                self.logger.info(f"Closing {position.side.value} position with MARKET order: {qty} {symbol}")
                
                order = await self.place_market_order(
                    side=side,
                    usdt_amount=None,  # Not used for closing
                    reduce_only=True,
                    symbol=symbol
                )
                
                return order is not None
            else:
                # Get current price
                ticker = self.client.get_ticker(symbol)
                if side == OrderSide.BUY:
                    # Use ask price + small buffer for buy orders
                    price = float(ticker.get("ask1Price", ticker.get("lastPrice", "0"))) * 1.001
                else:
                    # Use bid price - small buffer for sell orders
                    price = float(ticker.get("bid1Price", ticker.get("lastPrice", "0"))) * 0.999
                
                # Place limit order to close position
                self.logger.info(f"Closing {position.side.value} position with LIMIT order: {qty} {symbol} @ {price}")
                
                order = await self.place_limit_order(
                    side=side,
                    price=price,
                    usdt_amount=None,  # Not used for closing
                    reduce_only=True,
                    symbol=symbol
                )
                
                return order is not None
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return False
    
    async def close_all_positions(self, market: bool = True) -> bool:
        """
        Close all positions
        
        Args:
            market: Whether to use market orders (True) or limit orders (False)
            
        Returns:
            True if all closed successfully, False otherwise
        """
        try:
            # Get active positions
            active_positions = []
            for symbol, position in self.positions.items():
                if position.is_active():
                    active_positions.append(symbol)
            
            if not active_positions:
                self.logger.info("No active positions to close")
                return True
            
            self.logger.info(f"Closing {len(active_positions)} positions")
            
            # Close each position
            success = True
            for symbol in active_positions:
                if not await self.close_position(symbol, market):
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error closing all positions: {e}")
            return False
    
    def get_daily_pnl(self) -> float:
        """
        Get daily realized PnL
        
        Returns:
            Daily realized PnL in USDT
        """
        return self.today_realized_pnl
    
    def get_active_order_count(self) -> int:
        """
        Get number of active orders
        
        Returns:
            Number of active orders
        """
        return sum(1 for order in self.orders.values() 
                   if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED])
    
    def get_active_position_count(self) -> int:
        """
        Get number of active positions
        
        Returns:
            Number of active positions
        """
        return sum(1 for position in self.positions.values() if position.is_active())
    
    def get_order_status(self, order_link_id: str) -> Optional[OrderStatus]:
        """
        Get order status
        
        Args:
            order_link_id: Order link ID
            
        Returns:
            Order status if found, None otherwise
        """
        if order_link_id in self.orders:
            return self.orders[order_link_id].status
        return None
    
    async def apply_tp_sl(self, symbol: str, tp_price: float = None, sl_price: float = None) -> bool:
        """
        Apply take profit and stop loss to an existing position
        
        Args:
            symbol: Symbol to apply TP/SL for
            tp_price: Take profit price (None to remove)
            sl_price: Stop loss price (None to remove)
            
        Returns:
            True if applied successfully, False otherwise
        """
        position = self.positions.get(symbol)
        
        if not position or not position.is_active():
            self.logger.warning(f"No active position for {symbol}")
            return False
        
        try:
            # Set TP/SL via trading-stop endpoint
            params = {
                "category": "linear",
                "symbol": symbol,
                "positionIdx": 0  # One-way mode
            }
            
            if tp_price is not None:
                params["takeProfit"] = str(self._round_price(tp_price, symbol))
                
            if sl_price is not None:
                params["stopLoss"] = str(self._round_price(sl_price, symbol))
            
            self.logger.info(f"Applying TP/SL for {symbol} position - TP: {tp_price}, SL: {sl_price}")
            
            response = self.client._make_request(
                method="POST",
                endpoint="/v5/position/trading-stop",
                params=params
            )
            
            if response.get("retCode") == 0:
                self.logger.info(f"TP/SL applied successfully for {symbol}")
                
                # Update position
                if tp_price is not None:
                    position.take_profit = tp_price
                if sl_price is not None:
                    position.stop_loss = sl_price
                    
                return True
            else:
                self.logger.error(f"Failed to apply TP/SL: {response}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error applying TP/SL: {e}")
            return False
    
    async def update(self) -> bool:
        """
        Update order and position status
        
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Reset daily tracking if it's a new day
            current_date = datetime.now().date()
            if current_date != self.today_date:
                self.today_date = current_date
                self.today_filled_orders = []
                self.today_realized_pnl = 0.0
                self.logger.info(f"Reset daily tracking for {current_date}")
            
            # Update orders
            await self.update_all_orders()
            
            # Update positions
            await self.sync_positions()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating order manager: {e}")
            return False