#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
State Reconciliation Module

Handles synchronization between local state and exchange state
after disconnections or other failure scenarios.
"""

import logging
import time
from typing import Dict, List, Set, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ReconciliationResult(Enum):
    """Results of the reconciliation process."""
    SUCCESSFUL = "successful"               # All state reconciled correctly
    PARTIAL = "partial"                     # Some state reconciled
    FAILED = "failed"                       # Reconciliation failed
    NO_ACTION_NEEDED = "no_action_needed"   # States already in sync


class StateReconciler:
    """
    Reconciles internal bot state with exchange state.
    
    This component ensures data consistency between the local order/position 
    tracking and the actual state on the exchange, handling scenarios like 
    disconnections, API timeouts, and other failure modes.
    """
    
    def __init__(self, client, order_manager):
        """
        Initialize the state reconciler.
        
        Args:
            client: Bybit API client instance
            order_manager: OrderManager instance
        """
        self.client = client
        self.order_manager = order_manager
        self.reconciliation_in_progress = False
        self.last_reconciliation_time = 0
        self.min_reconciliation_interval = 5  # seconds
        
        # Statistics tracking
        self.reconciliation_attempts = 0
        self.successful_reconciliations = 0
        self.failed_reconciliations = 0
    
    def reconcile_state(self, force: bool = False) -> ReconciliationResult:
        """
        Reconcile local state with exchange state.
        
        Args:
            force: Force reconciliation even if recently performed
            
        Returns:
            ReconciliationResult enum indicating the outcome
        """
        # Prevent concurrent reconciliations
        if self.reconciliation_in_progress:
            logger.warning("State reconciliation already in progress, skipping")
            return ReconciliationResult.NO_ACTION_NEEDED
        
        # Rate limit reconciliation unless forced
        current_time = time.time()
        if not force and (current_time - self.last_reconciliation_time) < self.min_reconciliation_interval:
            logger.debug("Skipping reconciliation due to rate limiting")
            return ReconciliationResult.NO_ACTION_NEEDED
        
        try:
            self.reconciliation_in_progress = True
            self.reconciliation_attempts += 1
            self.last_reconciliation_time = current_time
            
            logger.info("Starting state reconciliation")
            
            # 1. Reconcile positions
            positions_result = self._reconcile_positions()
            
            # 2. Reconcile active orders
            orders_result = self._reconcile_orders()
            
            # Determine overall result
            if positions_result and orders_result:
                logger.info("State reconciliation completed successfully")
                self.successful_reconciliations += 1
                return ReconciliationResult.SUCCESSFUL
            elif positions_result or orders_result:
                logger.warning("State reconciliation partially completed")
                return ReconciliationResult.PARTIAL
            else:
                logger.error("State reconciliation failed")
                self.failed_reconciliations += 1
                return ReconciliationResult.FAILED
                
        except Exception as e:
            logger.exception(f"Error during state reconciliation: {str(e)}")
            self.failed_reconciliations += 1
            return ReconciliationResult.FAILED
        finally:
            self.reconciliation_in_progress = False
    
    def _reconcile_positions(self) -> bool:
        """
        Reconcile local position tracking with exchange positions.
        
        Returns:
            True if reconciliation successful, False otherwise
        """
        try:
            # 1. Get all positions from exchange
            exchange_positions = self._get_exchange_positions()
            if exchange_positions is None:
                logger.error("Failed to retrieve positions from exchange")
                return False
            
            # 2. Get local position tracking
            local_positions = self.order_manager.get_positions()
            
            # 3. Reconcile differences
            exchange_symbols = set(exchange_positions.keys())
            local_symbols = set(local_positions.keys())
            
            # Identify positions that exist on exchange but not locally
            missing_locally = exchange_symbols - local_symbols
            for symbol in missing_locally:
                position = exchange_positions[symbol]
                if float(position['size']) != 0:  # Only care about non-zero positions
                    logger.warning(f"Found position on exchange not tracked locally: {symbol}, size: {position['size']}")
                    # Update local tracking
                    self.order_manager.update_position_from_exchange(symbol, position)
            
            # Identify positions that exist locally but not on exchange
            missing_on_exchange = local_symbols - exchange_symbols
            for symbol in missing_on_exchange:
                position = local_positions[symbol]
                if position['size'] != 0:  # Only care about non-zero positions
                    logger.warning(f"Local position not found on exchange: {symbol}, size: {position['size']}")
                    # Clear local tracking
                    self.order_manager.update_position(symbol, 0, 0, "RECONCILIATION")
            
            # Reconcile positions that exist in both places
            for symbol in exchange_symbols.intersection(local_symbols):
                exchange_pos = exchange_positions[symbol]
                local_pos = local_positions[symbol]
                
                # Check if positions match
                exchange_size = float(exchange_pos['size'])
                local_size = float(local_pos['size'])
                
                if exchange_size != local_size:
                    logger.warning(
                        f"Position size mismatch for {symbol}: "
                        f"Exchange={exchange_size}, Local={local_size}"
                    )
                    # Update local tracking to match exchange
                    self.order_manager.update_position_from_exchange(symbol, exchange_pos)
            
            logger.info("Position reconciliation completed")
            return True
            
        except Exception as e:
            logger.exception(f"Error reconciling positions: {str(e)}")
            return False
    
    def _reconcile_orders(self) -> bool:
        """
        Reconcile local order tracking with exchange orders.
        
        Returns:
            True if reconciliation successful, False otherwise
        """
        try:
            # 1. Get all active orders from exchange
            exchange_orders = self._get_exchange_orders()
            if exchange_orders is None:
                logger.error("Failed to retrieve orders from exchange")
                return False
            
            # 2. Get local order tracking
            local_orders = self.order_manager.get_active_orders()
            
            # Create dictionaries keyed by order_id for easier comparison
            exchange_orders_dict = {order['order_id']: order for order in exchange_orders}
            local_orders_dict = {order['order_id']: order for order in local_orders}
            
            # 3. Reconcile differences
            exchange_order_ids = set(exchange_orders_dict.keys())
            local_order_ids = set(local_orders_dict.keys())
            
            # Identify orders that exist on exchange but not locally
            missing_locally = exchange_order_ids - local_order_ids
            for order_id in missing_locally:
                order = exchange_orders_dict[order_id]
                logger.warning(f"Found order on exchange not tracked locally: {order_id}, {order['symbol']}")
                # Add to local tracking
                self.order_manager.add_order_from_exchange(order)
            
            # Identify orders that exist locally but not on exchange
            missing_on_exchange = local_order_ids - exchange_order_ids
            for order_id in missing_on_exchange:
                order = local_orders_dict[order_id]
                logger.warning(f"Local order not found on exchange: {order_id}, {order['symbol']}")
                
                # Check status on exchange to determine what happened
                order_status = self._check_order_status(order_id)
                
                if order_status in ['FILLED', 'CANCELED', 'REJECTED']:
                    # Order was already processed, update local state
                    logger.info(f"Order {order_id} is {order_status} on exchange, updating local state")
                    self.order_manager.update_order_status(order_id, order_status)
                else:
                    # Order truly missing, mark as lost
                    logger.warning(f"Order {order_id} is missing on exchange, marking as lost")
                    self.order_manager.update_order_status(order_id, "LOST")
            
            # Check for state differences in orders that exist in both places
            for order_id in exchange_order_ids.intersection(local_order_ids):
                exchange_order = exchange_orders_dict[order_id]
                local_order = local_orders_dict[order_id]
                
                # Check if states match
                if exchange_order['status'] != local_order['status']:
                    logger.warning(
                        f"Order status mismatch for {order_id}: "
                        f"Exchange={exchange_order['status']}, Local={local_order['status']}"
                    )
                    # Update local tracking to match exchange
                    self.order_manager.update_order_status(
                        order_id, 
                        exchange_order['status'], 
                        exchange_order.get('filled_qty', 0),
                        exchange_order.get('avg_price', 0)
                    )
            
            logger.info("Order reconciliation completed")
            return True
            
        except Exception as e:
            logger.exception(f"Error reconciling orders: {str(e)}")
            return False
    
    def _get_exchange_positions(self) -> Optional[Dict[str, Any]]:
        """
        Get all positions from the exchange.
        
        Returns:
            Dictionary of positions keyed by symbol, or None if request failed
        """
        try:
            # API call to get positions
            positions_response = self.client.get_positions()
            
            if not positions_response or 'result' not in positions_response:
                logger.error("Invalid response from exchange when fetching positions")
                return None
            
            # Process response into a symbol-keyed dictionary
            positions = {}
            for position in positions_response['result']:
                symbol = position['symbol']
                positions[symbol] = position
            
            return positions
            
        except Exception as e:
            logger.exception(f"Error fetching positions from exchange: {str(e)}")
            return None
    
    def _get_exchange_orders(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all active orders from the exchange.
        
        Returns:
            List of active orders, or None if request failed
        """
        try:
            # API call to get active orders
            orders_response = self.client.get_active_orders()
            
            if not orders_response or 'result' not in orders_response:
                logger.error("Invalid response from exchange when fetching orders")
                return None
            
            return orders_response['result']
            
        except Exception as e:
            logger.exception(f"Error fetching orders from exchange: {str(e)}")
            return None
    
    def _check_order_status(self, order_id: str) -> str:
        """
        Check the status of a specific order.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Order status string, or "UNKNOWN" if not determinable
        """
        try:
            # API call to get order status
            order_response = self.client.get_order(order_id)
            
            if not order_response or 'result' not in order_response:
                logger.error(f"Invalid response from exchange when checking order {order_id}")
                return "UNKNOWN"
            
            order = order_response['result']
            return order.get('status', "UNKNOWN")
            
        except Exception as e:
            logger.exception(f"Error checking order status: {str(e)}")
            return "UNKNOWN"
    
    def get_reconciliation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about reconciliation operations.
        
        Returns:
            Dictionary of reconciliation statistics
        """
        return {
            'attempts': self.reconciliation_attempts,
            'successful': self.successful_reconciliations,
            'failed': self.failed_reconciliations,
            'success_rate': (self.successful_reconciliations / self.reconciliation_attempts 
                            if self.reconciliation_attempts > 0 else 0),
            'last_reconciliation': self.last_reconciliation_time
        }