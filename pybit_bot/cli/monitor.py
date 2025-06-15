#!/usr/bin/env python
"""
PyBit Bot Monitor - Real-time monitoring dashboard
"""
import os
import sys
import time
import curses
import json
import signal
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Global variables
running = True

def signal_handler(sig, frame):
    """Handle termination signals"""
    global running
    running = False

class BotMonitor:
    """Real-time monitoring dashboard for the PyBit Bot"""
    
    def __init__(self, refresh_rate=5):
        self.refresh_rate = refresh_rate
        self.status_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "status.json")
        self.log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
        
        # Initialize curses
        self.stdscr = None
        self.max_y = 0
        self.max_x = 0
        
        # Windows
        self.header_win = None
        self.status_win = None
        self.positions_win = None
        self.orders_win = None
        self.performance_win = None
        self.logs_win = None
    
    def start(self):
        """Start the monitoring dashboard"""
        curses.wrapper(self._main_loop)
    
    def _main_loop(self, stdscr):
        """Main loop for the dashboard"""
        global running
        
        # Setup
        self.stdscr = stdscr
        curses.curs_set(0)  # Hide cursor
        curses.start_color()
        curses.use_default_colors()
        
        # Define color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Green for positive values
        curses.init_pair(2, curses.COLOR_RED, -1)    # Red for negative values
        curses.init_pair(3, curses.COLOR_YELLOW, -1) # Yellow for warnings
        curses.init_pair(4, curses.COLOR_CYAN, -1)   # Cyan for headers
        
        # Main loop
        while running:
            # Get terminal size
            self.max_y, self.max_x = self.stdscr.getmaxyx()
            
            # Clear screen
            self.stdscr.clear()
            
            # Create windows
            self._create_windows()
            
            # Update windows
            self._update_header()
            self._update_status()
            self._update_positions()
            self._update_orders()
            self._update_performance()
            self._update_logs()
            
            # Refresh the screen
            self.stdscr.refresh()
            
            # Wait for key press or timeout
            key = self.stdscr.getch()
            
            # Handle key presses
            if key == ord('q'):
                running = False
            
            # Sleep for refresh rate
            time.sleep(self.refresh_rate)
    
    def _create_windows(self):
        """Create windows for the dashboard"""
        # Header (2 lines)
        self.header_win = curses.newwin(2, self.max_x, 0, 0)
        
        # Status (5 lines)
        self.status_win = curses.newwin(5, self.max_x, 2, 0)
        
        # Positions (height depends on number of positions, min 5)
        self.positions_win = curses.newwin(5, self.max_x, 7, 0)
        
        # Orders (height depends on number of orders, min 5)
        self.orders_win = curses.newwin(5, self.max_x, 12, 0)
        
        # Performance (5 lines)
        self.performance_win = curses.newwin(5, self.max_x, 17, 0)
        
        # Logs (remaining space)
        self.logs_win = curses.newwin(self.max_y - 22, self.max_x, 22, 0)
    
    def _update_header(self):
        """Update the header window"""
        self.header_win.clear()
        
        # Draw header
        self.header_win.addstr(0, 0, "PyBit Bot - Monitoring Dashboard", curses.A_BOLD | curses.color_pair(4))
        self.header_win.addstr(1, 0, f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
                              f"Press 'q' to quit", curses.A_BOLD)
        
        self.header_win.refresh()
    
    def _update_status(self):
        """Update the status window"""
        self.status_win.clear()
        
        # Draw border and title
        self.status_win.box()
        self.status_win.addstr(0, 2, "Bot Status", curses.A_BOLD | curses.color_pair(4))
        
        # Check if bot is running
        pid_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "pybit_bot.pid")
        is_running = os.path.exists(pid_file)
        
        # Get status data
        status_data = self._load_status_data()
        
        # Draw status info
        if is_running:
            self.status_win.addstr(1, 2, "Status: ", curses.A_BOLD)
            self.status_win.addstr("Running", curses.color_pair(1))
            
            if status_data:
                # Show additional status info
                if 'runtime' in status_data:
                    self.status_win.addstr(1, 30, f"Runtime: {status_data['runtime']}")
                
                if 'last_update' in status_data:
                    self.status_win.addstr(2, 2, f"Last Update: {status_data['last_update']}")
                
                if 'symbols' in status_data:
                    symbols = status_data.get('symbols', [])
                    symbols_str = ", ".join(symbols) if symbols else "None"
                    self.status_win.addstr(3, 2, f"Symbols: {symbols_str}")
        else:
            self.status_win.addstr(1, 2, "Status: ", curses.A_BOLD)
            self.status_win.addstr("Not Running", curses.color_pair(2))
        
        self.status_win.refresh()
    
    def _update_positions(self):
        """Update the positions window"""
        self.positions_win.clear()
        
        # Draw border and title
        self.positions_win.box()
        self.positions_win.addstr(0, 2, "Open Positions", curses.A_BOLD | curses.color_pair(4))
        
        # Get position data
        status_data = self._load_status_data()
        positions = status_data.get('positions', []) if status_data else []
        
        # Draw positions
        if positions:
            # Draw header
            self.positions_win.addstr(1, 2, "Symbol", curses.A_BOLD)
            self.positions_win.addstr(1, 12, "Side", curses.A_BOLD)
            self.positions_win.addstr(1, 20, "Size", curses.A_BOLD)
            self.positions_win.addstr(1, 30, "Entry", curses.A_BOLD)
            self.positions_win.addstr(1, 40, "Current", curses.A_BOLD)
            self.positions_win.addstr(1, 50, "PnL", curses.A_BOLD)
            self.positions_win.addstr(1, 60, "ROI", curses.A_BOLD)
            
            # Draw positions (limit to what fits in the window)
            max_positions = min(len(positions), self.positions_win.getmaxyx()[0] - 3)
            
            for i in range(max_positions):
                pos = positions[i]
                symbol = pos.get('symbol', 'N/A')
                side = pos.get('side', 'N/A')
                size = pos.get('size', '0')
                entry = pos.get('entryPrice', '0')
                current = pos.get('markPrice', '0')
                pnl = pos.get('unrealisedPnl', '0')
                
                # Calculate ROI
                try:
                    entry_float = float(entry)
                    pnl_float = float(pnl)
                    size_float = float(size)
                    
                    if entry_float > 0 and size_float > 0:
                        roi = (pnl_float / (entry_float * size_float)) * 100
                    else:
                        roi = 0
                except:
                    roi = 0
                
                # Draw row
                self.positions_win.addstr(2 + i, 2, symbol)
                self.positions_win.addstr(2 + i, 12, side)
                self.positions_win.addstr(2 + i, 20, size)
                self.positions_win.addstr(2 + i, 30, entry)
                self.positions_win.addstr(2 + i, 40, current)
                
                # Color PnL based on value
                try:
                    pnl_float = float(pnl)
                    color = curses.color_pair(1) if pnl_float >= 0 else curses.color_pair(2)
                    self.positions_win.addstr(2 + i, 50, pnl, color)
                except:
                    self.positions_win.addstr(2 + i, 50, pnl)
                
                # Color ROI based on value
                color = curses.color_pair(1) if roi >= 0 else curses.color_pair(2)
                self.positions_win.addstr(2 + i, 60, f"{roi:.2f}%", color)
        else:
            self.positions_win.addstr(1, 2, "No open positions")
        
        self.positions_win.refresh()
    
    def _update_orders(self):
        """Update the orders window"""
        self.orders_win.clear()
        
        # Draw border and title
        self.orders_win.box()
        self.orders_win.addstr(0, 2, "Open Orders", curses.A_BOLD | curses.color_pair(4))
        
        # Get order data
        status_data = self._load_status_data()
        orders = status_data.get('orders', []) if status_data else []
        
        # Draw orders
        if orders:
            # Draw header
            self.orders_win.addstr(1, 2, "Symbol", curses.A_BOLD)
            self.orders_win.addstr(1, 12, "Type", curses.A_BOLD)
            self.orders_win.addstr(1, 20, "Side", curses.A_BOLD)
            self.orders_win.addstr(1, 30, "Size", curses.A_BOLD)
            self.orders_win.addstr(1, 40, "Price", curses.A_BOLD)
            self.orders_win.addstr(1, 50, "Status", curses.A_BOLD)
            self.orders_win.addstr(1, 60, "Time", curses.A_BOLD)
            
            # Draw orders (limit to what fits in the window)
            max_orders = min(len(orders), self.orders_win.getmaxyx()[0] - 3)
            
            for i in range(max_orders):
                order = orders[i]
                symbol = order.get('symbol', 'N/A')
                type_ = order.get('orderType', 'N/A')
                side = order.get('side', 'N/A')
                size = order.get('qty', '0')
                price = order.get('price', '0')
                status = order.get('orderStatus', 'N/A')
                
                # Convert timestamp to readable format
                try:
                    timestamp = int(order.get('createdTime', 0)) / 1000
                    time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
                except:
                    time_str = 'N/A'
                
                # Draw row
                self.orders_win.addstr(2 + i, 2, symbol)
                self.orders_win.addstr(2 + i, 12, type_)
                
                # Color side based on value
                color = curses.color_pair(1) if side == 'Buy' else curses.color_pair(2)
                self.orders_win.addstr(2 + i, 20, side, color)
                
                self.orders_win.addstr(2 + i, 30, size)
                self.orders_win.addstr(2 + i, 40, price)
                self.orders_win.addstr(2 + i, 50, status)
                self.orders_win.addstr(2 + i, 60, time_str)
        else:
            self.orders_win.addstr(1, 2, "No open orders")
        
        self.orders_win.refresh()
    
    def _update_performance(self):
        """Update the performance window"""
        self.performance_win.clear()
        
        # Draw border and title
        self.performance_win.box()
        self.performance_win.addstr(0, 2, "Performance", curses.A_BOLD | curses.color_pair(4))
        
        # Get performance data
        status_data = self._load_status_data()
        performance = status_data.get('performance', {}) if status_data else {}
        
        # Draw performance info
        if performance:
            self.performance_win.addstr(1, 2, f"Signals Generated: {performance.get('signals_generated', 0)}")
            self.performance_win.addstr(2, 2, f"Orders Placed: {performance.get('orders_placed', 0)}")
            self.performance_win.addstr(1, 40, f"Orders Filled: {performance.get('orders_filled', 0)}")
            
            # Color errors based on count
            errors = performance.get('errors', 0)
            color = curses.color_pair(1) if errors == 0 else curses.color_pair(2)
            self.performance_win.addstr(2, 40, f"Errors: {errors}", color)
        else:
            self.performance_win.addstr(1, 2, "No performance data available")
        
        self.performance_win.refresh()
    
    def _update_logs(self):
        """Update the logs window"""
        self.logs_win.clear()
        
        # Draw border and title
        self.logs_win.box()
        self.logs_win.addstr(0, 2, "Recent Logs", curses.A_BOLD | curses.color_pair(4))
        
        # Get log data (read from most recent log file)
        log_file = self._get_latest_log_file()
        log_lines = self._read_log_file(log_file, max_lines=self.logs_win.getmaxyx()[0] - 3)
        
        # Draw logs
        if log_lines:
            for i, line in enumerate(log_lines):
                # Skip if we've reached the bottom of the window
                if i >= self.logs_win.getmaxyx()[0] - 3:
                    break
                
                # Truncate line if it's too long
                max_len = self.logs_win.getmaxyx()[1] - 4
                if len(line) > max_len:
                    line = line[:max_len - 3] + "..."
                
                # Color the line based on content
                color = curses.A_NORMAL
                if "ERROR" in line:
                    color = curses.color_pair(2)  # Red for errors
                elif "WARNING" in line:
                    color = curses.color_pair(3)  # Yellow for warnings
                elif "INFO" in line:
                    color = curses.color_pair(4)  # Cyan for info
                
                self.logs_win.addstr(1 + i, 2, line, color)
        else:
            self.logs_win.addstr(1, 2, "No logs available")
        
        self.logs_win.refresh()
    
    def _load_status_data(self):
        """Load status data from the status file"""
        if not os.path.exists(self.status_file):
            return None
        
        try:
            with open(self.status_file, 'r') as f:
                return json.load(f)
        except:
            return None
    
    def _get_latest_log_file(self):
        """Get the path to the latest log file"""
        if not os.path.exists(self.log_dir):
            return None
        
        # Get log files sorted by modification time (newest first)
        log_files = [os.path.join(self.log_dir, f) for f in os.listdir(self.log_dir) if f.endswith('.log')]
        log_files.sort(key=os.path.getmtime, reverse=True)
        
        return log_files[0] if log_files else None
    
    def _read_log_file(self, log_file, max_lines=10):
        """Read the last N lines from a log file"""
        if not log_file or not os.path.exists(log_file):
            return []
        
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-max_lines:]]
        except:
            return []

def start_monitor(args, logger):
    """Start the monitoring dashboard"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the monitor
    monitor = BotMonitor(refresh_rate=args.refresh)
    monitor.start()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="PyBit Bot Monitor")
    parser.add_argument("--refresh", "-r", type=int, default=5, help="Refresh rate in seconds")
    
    args = parser.parse_args()
    start_monitor(args, None)

if __name__ == "__main__":
    main()