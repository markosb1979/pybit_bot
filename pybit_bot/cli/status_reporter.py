"""
PyBit Bot Status Reporter - Generate and update status information
"""
import os
import sys
import json
import time
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class StatusReporter:
    """Generate and update status information for the bot"""
    
    def __init__(self, engine):
        self.engine = engine
        self.status_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot")
        self.status_file = os.path.join(self.status_dir, "status.json")
        
        # Create status directory if it doesn't exist
        os.makedirs(self.status_dir, exist_ok=True)
    
    def update(self):
        """Update the status file with current engine state"""
        try:
            # Build status data
            status = self._build_status()
            
            # Write to file
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Failed to update status: {str(e)}")
            return False
    
    def _build_status(self):
        """Build status data from engine state"""
        status = {
            'is_running': self.engine.is_running if hasattr(self.engine, 'is_running') else False,
            'start_time': self.engine.start_time.isoformat() if hasattr(self.engine, 'start_time') and self.engine.start_time else None,
            'runtime': str(datetime.now() - self.engine.start_time) if hasattr(self.engine, 'start_time') and self.engine.start_time else None,
            'symbols': self.engine.symbols if hasattr(self.engine, 'symbols') else [],
            'performance': self.engine.performance if hasattr(self.engine, 'performance') else {},
            'last_update': datetime.now().isoformat()
        }
        
        # Add positions and orders if available
        if hasattr(self.engine, 'order_manager') and self.engine.order_manager:
            try:
                status['positions'] = self.engine.order_manager.get_positions()
            except:
                status['positions'] = []
            
            try:
                status['orders'] = self.engine.order_manager.get_open_orders()
            except:
                status['orders'] = []
        
        return status

def start_reporter(engine, interval=5):
    """Start a status reporter in a separate thread"""
    import threading
    
    reporter = StatusReporter(engine)
    
    def update_loop():
        while True:
            reporter.update()
            time.sleep(interval)
    
    thread = threading.Thread(target=update_loop, daemon=True)
    thread.start()
    
    return thread