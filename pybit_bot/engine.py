def start(self, test_mode=False):
    """
    Start the trading engine.
    
    Args:
        test_mode: If True, skip actual event loop creation for testing
        
    Returns:
        True if started successfully, False otherwise
    """
    if self.is_running:
        self.logger.warning("Trading engine is already running")
        print("WARNING: Engine already running")
        return False
        
    self.logger.info("Starting trading engine...")
    print("Starting trading engine...")
    
    try:
        print("Step 1: Setting engine state...")
        # Set state
        self.is_running = True
        self.start_time = datetime.now()
        self._stop_event.clear()
        
        # Skip event loop creation in test mode
        if not test_mode:
            print("Step 2: Creating new event loop...")
            # Create new asyncio event loop for this thread
            try:
                self._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._event_loop)
                print("Event loop created successfully")
            except Exception as e:
                print(f"ERROR creating event loop: {str(e)}")
                raise
            
            print("Step 3: Starting market data manager...")
            # Start market data manager
            if hasattr(self.market_data_manager, 'start'):
                try:
                    self.market_data_manager.start()
                    print("Market data manager started")
                except Exception as e:
                    print(f"ERROR starting market data manager: {str(e)}")
                    raise
            
            print("Step 4: Creating main thread...")
            # Start main loop in a separate thread
            try:
                self._main_thread = threading.Thread(target=self._main_loop_wrapper, daemon=True)
                print("Thread created, starting...")
                self._main_thread.start()
                print("Main thread started successfully")
            except Exception as e:
                print(f"ERROR creating/starting main thread: {str(e)}")
                raise
        else:
            # In test mode, just set basic properties without actual event loop
            print("Running in test mode - skipping event loop and thread creation")
            from unittest.mock import MagicMock
            self._event_loop = MagicMock()
            self._main_thread = MagicMock()
        
        self.logger.info("Trading engine started")
        print("Trading engine started successfully")
        return True
        
    except Exception as e:
        self.logger.error(f"Error starting trading engine: {str(e)}")
        print(f"ERROR starting engine: {str(e)}")
        traceback.print_exc()
        self.stop()
        return False