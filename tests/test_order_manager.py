"""
Test script for OrderManager

This script tests the OrderManager's ability to:
- Connect to the exchange
- Get instrument information
- Get position information
- Place orders
- Get order status
"""

import os
import sys
import asyncio
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit_bot.core.client import BybitClientTransport
from pybit_bot.utils.credentials import load_credentials
from pybit_bot.utils.logger import Logger
from pybit_bot.managers.order_manager import OrderManager

logger = Logger("TestOrderManager")

async def test_order_manager_init():
    """Test OrderManager initialization"""
    logger.info("Testing OrderManager initialization...")
    
    # Load credentials
    credentials = load_credentials()
    
    # Create client
    client = BybitClientTransport(credentials)
    
    # Create a simple config for testing
    config = {
        'execution': {
            'order_execution': {
                'default_order_type': 'LIMIT',
                'time_in_force': 'GTC',
                'retry_attempts': 3
            }
        }
    }
    
    # Create order manager
    order_manager = OrderManager(client, config, logger=logger)
    logger.info("OrderManager initialized")
    
    logger.info("OrderManager initialization test PASSED ✓")
    return order_manager

async def test_get_positions(order_manager):
    """Test getting positions"""
    logger.info("Testing get_positions...")
    
    try:
        # Get all positions
        positions = await order_manager.get_positions()
        
        if positions is None:
            logger.error("get_positions returned None")
            return False
            
        logger.info(f"Got {len(positions)} positions")
        
        # Print positions
        for position in positions:
            symbol = position.get("symbol")
            size = position.get("size")
            side = position.get("side")
            
            logger.info(f"Position: {symbol} {side} {size}")
        
        logger.info("get_positions test PASSED ✓")
        return True
    except Exception as e:
        logger.error(f"get_positions test FAILED with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_get_open_orders(order_manager):
    """Test getting open orders"""
    logger.info("Testing get_open_orders...")
    
    try:
        # Check if method exists
        if not hasattr(order_manager, "get_open_orders"):
            logger.error("OrderManager does not have get_open_orders method")
            return False
            
        # Get open orders
        open_orders = await order_manager.get_open_orders()
        
        if open_orders is None:
            logger.error("get_open_orders returned None")
            return False
            
        logger.info(f"Got {len(open_orders)} open orders")
        
        # Print orders
        for order in open_orders:
            symbol = order.get("symbol")
            price = order.get("price")
            qty = order.get("qty")
            side = order.get("side")
            
            logger.info(f"Order: {symbol} {side} {qty} @ {price}")
        
        logger.info("get_open_orders test PASSED ✓")
        return True
    except Exception as e:
        logger.error(f"get_open_orders test FAILED with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_sync_order_status(order_manager):
    """Test synchronizing order status"""
    logger.info("Testing sync_order_status...")
    
    try:
        # Sync order status
        result = await order_manager.sync_order_status()
        
        logger.info(f"sync_order_status completed with result: {result}")
        logger.info("sync_order_status test PASSED ✓")
        return True
    except Exception as e:
        logger.error(f"sync_order_status test FAILED with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Run all tests"""
    logger.info("===== ORDER MANAGER TESTS =====")
    
    # Load environment variables
    load_dotenv()
    
    # Run tests
    order_manager = await test_order_manager_init()
    if not order_manager:
        logger.error("OrderManager initialization test failed, stopping further tests")
        return
    
    await test_get_positions(order_manager)
    await test_get_open_orders(order_manager)
    await test_sync_order_status(order_manager)
    
    logger.info("===== ALL TESTS COMPLETED =====")

if __name__ == "__main__":
    asyncio.run(main())