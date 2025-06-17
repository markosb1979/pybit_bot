async def _handle_signals(self, symbol: str, signals: List[TradeSignal]):
    """
    Process trading signals for a symbol.
    
    Args:
        symbol: Trading symbol
        signals: List of trade signals
    """
    for signal in signals:
        try:
            # Track signals
            self.performance['signals_generated'] += 1
            
            # Log the signal
            self.logger.info(f"Signal generated for {symbol}: {signal.signal_type} {signal.direction}")
            print(f"SIGNAL: {symbol} {signal.signal_type} {signal.direction}")
            
            # Store recent signal
            signal_key = f"{symbol}_{signal.signal_type}"
            self.recent_signals[signal_key] = {
                'signal': signal,
                'timestamp': datetime.now()
            }
            
            # Check if we can take this trade
            can_take_trade = await self._can_take_trade(symbol, signal)
            if not can_take_trade:
                self.logger.info(f"Skipping signal for {symbol}: position limit or other restriction")
                print(f"SKIP: Signal for {symbol} (position limit/restriction)")
                continue
            
            # Execute the signal
            print(f"Executing signal for {symbol}...")
            await self._execute_signal(symbol, signal)
            
        except Exception as e:
            self.logger.error(f"Error handling signal for {symbol}: {str(e)}")
            print(f"ERROR handling signal for {symbol}: {str(e)}")
            traceback.print_exc()