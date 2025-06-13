#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Market Simulator

Simulates market conditions for backtesting, including order matching,
slippage, and liquidity constraints.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
import logging

# Setup logging
logger = logging.getLogger(__name__)


class MarketSimulator:
    """Simulates market conditions for backtesting."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the market simulator.
        
        Args:
            config: Configuration dictionary with simulation parameters
        """
        self.config = config or {}
        
        # Default simulation parameters
        self.default_slippage = self.config.get('default_slippage_pct', 0.05) / 100
        self.default_commission = self.config.get('default_commission_pct', 0.075) / 100
        self.default_reject_prob = self.config.get('default_order_reject_probability', 0.0)
        self.liquidity_factor = self.config.get('liquidity_factor', 1.0)
        
        # Market state
        self.order_book = {}  # Simulated order book for each symbol
        self.ticker_data = {}  # Current ticker data for each symbol
        
    def update_market_data(self, symbol: str, data: Dict[str, Any]):
        """
        Update market data for a symbol.
        
        Args:
            symbol: Trading symbol
            data: Market data dictionary (OHLCV, etc.)
        """
        self.ticker_data[symbol] = data
        
        # Optionally simulate order book from OHLCV data
        self._simulate_order_book(symbol, data)
    
    def _simulate_order_book(self, symbol: str, data: Dict[str, Any]):
        """
        Simulate an order book from OHLCV data.
        
        Args:
            symbol: Trading symbol
            data: Market data dictionary
        """
        if 'close' not in data:
            return
            
        close_price = data['close']
        
        # Simple order book simulation
        # In a real implementation, this would be more sophisticated
        spread = close_price * 0.001 * (1 / self.liquidity_factor)
        
        bid_price = close_price - (spread / 2)
        ask_price = close_price + (spread / 2)
        
        # Calculate volume distribution
        base_volume = data.get('volume', 1000)
        
        # Create simulated order book
        self.order_book[symbol] = {
            'bids': [
                (bid_price * (1 - 0.0005 * i), base_volume * np.exp(-0.1 * i) * np.random.uniform(0.8, 1.2))
                for i in range(10)
            ],
            'asks': [
                (ask_price * (1 + 0.0005 * i), base_volume * np.exp(-0.1 * i) * np.random.uniform(0.8, 1.2))
                for i in range(10)
            ]
        }
    
    def execute_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate order execution with realistic market effects.
        
        Args:
            order: Order details dictionary
            
        Returns:
            Execution result dictionary
        """
        symbol = order.get('symbol')
        side = order.get('side', '').upper()  # BUY or SELL
        order_type = order.get('type', '').upper()  # LIMIT, MARKET
        qty = order.get('qty', 0.0)
        price = order.get('price')
        time_in_force = order.get('time_in_force', 'GTC')
        
        # Check if we have market data for this symbol
        if symbol not in self.ticker_data:
            return self._create_error_response("No market data available for symbol")
        
        # Random order rejection (simulates exchange issues)
        if np.random.random() < self.default_reject_prob:
            return self._create_error_response("Order rejected (simulated exchange issue)")
        
        # Get current market price
        current_price = self.ticker_data[symbol].get('close')
        
        # Determine execution price based on order type
        if order_type == 'MARKET':
            # Apply slippage for market orders
            slippage_factor = 1 + (self.default_slippage * (1 if side == 'BUY' else -1))
            execution_price = current_price * slippage_factor
        elif order_type == 'LIMIT':
            # For simplicity, assume limit orders are filled at the limit price
            # if the price is favorable compared to the current price
            if price is None:
                return self._create_error_response("Limit order must have a price")
                
            if (side == 'BUY' and price < current_price) or (side == 'SELL' and price > current_price):
                # Price is not favorable, order remains open
                if time_in_force == 'IOC':  # Immediate or Cancel
                    return self._create_error_response("Order not filled (price not favorable, IOC)")
                else:
                    return {
                        'status': 'OPEN',
                        'order_id': f"sim_{np.random.randint(10000, 99999)}",
                        'symbol': symbol,
                        'side': side,
                        'type': order_type,
                        'qty': qty,
                        'price': price,
                        'filled_qty': 0.0,
                        'avg_price': 0.0,
                        'message': "Order placed, waiting for execution"
                    }
            
            execution_price = price
        else:
            return self._create_error_response(f"Unsupported order type: {order_type}")
        
        # Calculate execution value
        execution_value = qty * execution_price
        
        # Apply commission
        commission = execution_value * self.default_commission
        
        # Create execution report
        execution = {
            'status': 'FILLED',
            'order_id': f"sim_{np.random.randint(10000, 99999)}",
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'qty': qty,
            'price': price,  # Original order price
            'filled_qty': qty,
            'avg_price': execution_price,  # Actual execution price
            'commission': commission,
            'execution_time': pd.Timestamp.now().isoformat(),
            'message': "Order filled successfully"
        }
        
        return execution
    
    def check_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Check the status of an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status dictionary
        """
        # In a real implementation, this would track orders
        # For now, just return a placeholder
        return {
            'status': 'UNKNOWN',
            'order_id': order_id,
            'message': "Order status unknown in simulation"
        }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Cancellation result dictionary
        """
        # In a real implementation, this would find and cancel the order
        # For now, just return a success response
        return {
            'status': 'CANCELED',
            'order_id': order_id,
            'message': "Order canceled successfully"
        }
    
    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """
        Create an error response.
        
        Args:
            message: Error message
            
        Returns:
            Error response dictionary
        """
        return {
            'status': 'ERROR',
            'message': message
        }