"""
Command-line monitoring interface for the trading bot
"""

import asyncio
import argparse
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pybit_bot.utils.logger import Logger


class BotMonitor:
    """Monitor for the trading bot"""
    
    def __init__(self, log_path=None):
        """
        Initialize the monitor
        
        Args:
            log_path: Path to log file directory
        """
        self.logger = Logger("BotMonitor")
        self.log_path = log_path or "logs"
        
        # Ensure log directory exists
        os.makedirs(self.log_path, exist_ok=True)
    
    async def start(self):
        """Start the monitoring process"""
        self.logger.info("Bot monitor started")
        
        try:
            while True:
                self._display_status()
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Monitor stopped")
        except Exception as e:
            self.logger.error(f"Error in monitor: {str(e)}")
    
    def _display_status(self):
        """Display current bot status"""
        # Clear the console
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 50)
        print(f"PyBit Bot Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # Check if the bot is running by looking for a PID file
        if os.path.exists(os.path.join(self.log_path, "bot.pid")):
            with open(os.path.join(self.log_path, "bot.pid"), "r") as f:
                pid = f.read().strip()
                
            # Check if process is running
            try:
                os.kill(int(pid), 0)
                print(f"Bot Status: RUNNING (PID: {pid})")
            except OSError:
                print("Bot Status: NOT RUNNING (stale PID file)")
        else:
            print("Bot Status: NOT RUNNING")
        
        # Display latest log entries
        print("\nLatest Log Entries:")
        print("-" * 50)
        
        log_files = [f for f in os.listdir(self.log_path) if f.endswith(".log")]
        if log_files:
            latest_log = max(log_files, key=lambda x: os.path.getmtime(os.path.join(self.log_path, x)))
            log_path = os.path.join(self.log_path, latest_log)
            
            # Display last 10 lines of log
            try:
                with open(log_path, "r") as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        print(line.strip())
            except Exception as e:
                print(f"Error reading log file: {str(e)}")
        else:
            print("No log files found")
        
        # Display positions if available
        positions_file = os.path.join(self.log_path, "positions.json")
        if os.path.exists(positions_file):
            print("\nCurrent Positions:")
            print("-" * 50)
            
            try:
                with open(positions_file, "r") as f:
                    positions = json.load(f)
                    
                if positions:
                    for symbol, pos in positions.items():
                        print(f"{symbol}: {pos['side']} {pos['size']} @ {pos['entry_price']}")
                else:
                    print("No open positions")
            except Exception as e:
                print(f"Error reading positions file: {str(e)}")
        
        print("\nPress Ctrl+C to exit monitor")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="PyBit Bot Monitor")
    
    parser.add_argument(
        "--log-path", 
        type=str, 
        help="Path to log directory"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    monitor = BotMonitor(log_path=args.log_path)
    asyncio.run(monitor.start())