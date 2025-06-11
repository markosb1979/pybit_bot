"""
Strategy Manager - orchestrates loading, running and managing trading strategies.
Coordinates between signal generation and order execution via OrderManager.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Union
import pandas as pd
from threading import Thread, Event

from strategies.base_strategy import BaseStrategy, TradeSignal, SignalType, OrderType
from utils.state_persistence import StatePersistence


class StrategyManager:
    """
    Manages the loading, execution and state of trading strategies.
    """
    
    def __init__(
        self,
        config: Dict,
        order_manager,
        data_manager,
        tpsl_manager=None,
        state_persistence: Optional[StatePersistence] = None
    ):
        """
        Initialize the strategy manager.
        
        Args:
            config: Main configuration dictionary
            order_manager: OrderManager instance for executing trades
            data_manager: DataManager instance for fetching market data
            tpsl_manager: TPSLManager for managing take-profit/stop-loss
            state_persistence: StatePersistence instance for saving/loading state
        """
        self.config = config
        self.order_manager = order_manager
        self.data_manager = data_manager
        self.tpsl_manager = tpsl_manager
        self.state_persistence = state_persistence
        
        self.logger = logging.getLogger(__name__)
        self.strategies: Dict[str, BaseStrategy] = {}
        self.active_signals: Dict[str, TradeSignal] = {}
        self.running = False
        self.loop_interval = self.config.get('strategy_loop_interval', 5)  # seconds
        self.stop_event = Event()
        self.strategy_thread = None
    
    def load_strategies(self, strategy_instances: List[BaseStrategy]) -> None:
        """
        Load strategy instances to be executed.
        
        Args:
            strategy_instances: List of BaseStrategy instances
        """
        for strategy in strategy_instances:
            self.strategies[strategy.name] = strategy
            self.logger.info(f"Loaded strategy: {strategy.name}")
    
    def _strategy_loop(self) -> None:
        """
        Main strategy loop that periodically checks for signals.
        """
        self.logger.info("Strategy loop started")
        
        while not self.stop_event.is_set() and self.running:
            try:
                # Get latest data for all required timeframes
                timeframes = self._get_required_timeframes()
                data = self._fetch_market_data(timeframes)
                
                # Process each strategy
                for strategy_name, strategy in self.strategies.items():
                    if not strategy.is_active:
                        continue
                    
                    # Calculate indicators
                    data_with_indicators = strategy.calculate_indicators(data)
                    
                    # Generate signals
                    signals = strategy.generate_signals(data_with_indicators)
                    
                    # Process signals
                    for signal in signals:
                        self._process_signal(signal, strategy_name)
                
                # Save state if configured
                if self.state_persistence:
                    self._save_state()
                
            except Exception as e:
                self.logger.error(f"Error in strategy loop: {str(e)}", exc_info=True)
            
            # Sleep until next check
            time.sleep(self.loop_interval)
        
        self.logger.info("Strategy loop stopped")
    
    def _get_required_timeframes(self) -> List[str]:
        """
        Get all unique timeframes required by loaded strategies.
        
        Returns:
            List of timeframe strings
        """
        timeframes = set()
        for strategy in self.strategies.values():
            timeframes.update(strategy.get_required_timeframes())
        return list(timeframes)
    
    def _fetch_market_data(self, timeframes: List[str]) -> Dict[str, pd.DataFrame]:
        """
        Fetch market data for all required timeframes.
        
        Args:
            timeframes: List of timeframe strings
            
        Returns:
            Dictionary of DataFrames with market data
        """
        data = {}
        for tf in timeframes:
            # Assuming data_manager has a get_candles method
            df = self.data_manager.get_candles(
                symbol=self.config.get('symbol', 'BTCUSDT'),
                interval=tf,
                limit=self.config.get('lookback_period', 100)
            )
            data[tf] = df
        return data
    
    def _process_signal(self, signal: TradeSignal, strategy_name: str) -> None:
        """
        Process a trading signal and execute orders if needed.
        
        Args:
            signal: TradeSignal object
            strategy_name: Name of the strategy generating the signal
        """
        if signal.signal_type == SignalType.NONE:
            return
        
        self.logger.info(f"Processing signal from {strategy_name}: {signal}")
        
        # Store signal for tracking
        signal_key = f"{strategy_name}_{signal.symbol}_{signal.signal_type.value}"
        self.active_signals[signal_key] = signal
        
        # Execute the trade based on signal type
        if signal.signal_type in [SignalType.BUY, SignalType.SELL]:
            self._execute_entry(signal)
        elif signal.signal_type in [SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT]:
            self._execute_exit(signal)
    
    def _execute_entry(self, signal: TradeSignal) -> None:
        """
        Execute an entry order based on the signal.
        
        Args:
            signal: TradeSignal object for entry
        """
        # Determine order side
        side = "Buy" if signal.signal_type == SignalType.BUY else "Sell"
        
        # Execute the order through order_manager
        if signal.order_type == OrderType.MARKET:
            order_result = self.order_manager.place_market_order(
                symbol=signal.symbol,
                side=side,
                quantity=signal.quantity
            )
        else:  # LIMIT order
            order_result = self.order_manager.place_limit_order(
                symbol=signal.symbol,
                side=side,
                quantity=signal.quantity,
                price=signal.price
            )
        
        # If order was placed successfully and we have a TPSL manager
        if order_result and self.tpsl_manager and 'order_id' in order_result:
            # Register the order with TPSL manager
            self.tpsl_manager.register_entry_order(
                order_id=order_result['order_id'],
                symbol=signal.symbol,
                side=side,
                entry_price=signal.price,
                quantity=signal.quantity,
                sl_price=signal.sl_price,
                tp_price=signal.tp_price
            )
    
    def _execute_exit(self, signal: TradeSignal) -> None:
        """
        Execute an exit order based on the signal.
        
        Args:
            signal: TradeSignal object for exit
        """
        # Determine position side to close
        is_long = signal.signal_type == SignalType.CLOSE_LONG
        side = "Sell" if is_long else "Buy"
        
        # Execute the order through order_manager
        order_result = self.order_manager.place_market_order(
            symbol=signal.symbol,
            side=side,
            reduce_only=True,
            quantity=signal.quantity
        )
        
        # If using TPSL manager, notify about the manual exit
        if order_result and self.tpsl_manager and 'order_id' in order_result:
            self.tpsl_manager.handle_manual_exit(
                symbol=signal.symbol,
                side=side,
                order_id=order_result['order_id']
            )
    
    def start(self) -> None:
        """
        Start the strategy execution in a separate thread.
        """
        if self.running:
            self.logger.warning("Strategy manager is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.strategy_thread = Thread(target=self._strategy_loop, daemon=True)
        self.strategy_thread.start()
        self.logger.info("Strategy manager started")
    
    def stop(self) -> None:
        """
        Stop the strategy execution.
        """
        if not self.running:
            return
        
        self.logger.info("Stopping strategy manager")
        self.running = False
        self.stop_event.set()
        
        if self.strategy_thread and self.strategy_thread.is_alive():
            self.strategy_thread.join(timeout=5.0)
        
        # Save final state
        if self.state_persistence:
            self._save_state()
    
    def _save_state(self) -> None:
        """
        Save the current state of all strategies.
        """
        if not self.state_persistence:
            return
        
        state = {
            'strategies': {name: strategy.get_state() for name, strategy in self.strategies.items()},
            'active_signals': {k: vars(v) for k, v in self.active_signals.items()},
            'timestamp': int(time.time())
        }
        
        self.state_persistence.save_state('strategy_manager', state)
    
    def restore_state(self) -> None:
        """
        Restore state from persistence.
        """
        if not self.state_persistence:
            return
        
        state = self.state_persistence.load_state('strategy_manager')
        if not state:
            self.logger.info("No strategy state to restore")
            return
        
        # Restore strategy states
        for name, strategy_state in state.get('strategies', {}).items():
            if name in self.strategies:
                self.strategies[name].restore_state(strategy_state)
                self.logger.info(f"Restored state for strategy: {name}")
        
        # Active signals can't be directly restored as they're objects
        # They will be regenerated on the next loop cycle
        
        self.logger.info(f"Restored strategy manager state from {state.get('timestamp', 'unknown')}")