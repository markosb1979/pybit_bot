"""
Simple Monitor for Windows - No curses dependency
"""
import os
import sys
import json
import time
import colorama
from datetime import datetime
from colorama import Fore, Style, Back

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize colorama
colorama.init()

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def read_status_file():
    """Read the status file"""
    status_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "status.json")
    if not os.path.exists(status_file):
        return None
    
    try:
        with open(status_file, 'r') as f:
            return json.load(f)
    except:
        return None

def read_log_lines(max_lines=10):
    """Read the last N lines from the latest log file"""
    log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
    if not os.path.exists(log_dir):
        return []
    
    # Get log files sorted by modification time (newest first)
    log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.log')]
    log_files.sort(key=os.path.getmtime, reverse=True)
    
    if not log_files:
        return []
    
    log_file = log_files[0]
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            return lines[-max_lines:] if len(lines) > max_lines else lines
    except:
        return []

def is_bot_running():
    """Check if the bot is running"""
    pid_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "pybit_bot.pid")
    if not os.path.exists(pid_file):
        return False, None
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        import psutil
        try:
            process = psutil.Process(pid)
            if process.is_running() and "python" in process.name().lower():
                return True, pid
        except:
            pass
        
        # If we get here, process doesn't exist
        os.remove(pid_file)
    except:
        pass
    
    return False, None

def format_time(time_str):
    """Format time string"""
    if not time_str:
        return "N/A"
    
    try:
        if isinstance(time_str, str) and 'T' in time_str:
            # ISO format
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return time_str
    except:
        return time_str

def print_header():
    """Print the dashboard header"""
    print(f"{Back.BLUE}{Fore.WHITE}PyBit Bot - Simple Monitoring Dashboard{Style.RESET_ALL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

def print_status():
    """Print bot status"""
    is_running, pid = is_bot_running()
    
    print(f"\n{Fore.CYAN}Bot Status:{Style.RESET_ALL}")
    if is_running:
        print(f"  Running: {Fore.GREEN}Yes{Style.RESET_ALL}")
        print(f"  PID: {pid}")
        
        # Get additional status info
        status_data = read_status_file()
        if status_data:
            print(f"  Start Time: {format_time(status_data.get('start_time'))}")
            print(f"  Runtime: {status_data.get('runtime', 'N/A')}")
            
            symbols = status_data.get('symbols', [])
            symbols_str = ", ".join(symbols) if symbols else "None"
            print(f"  Symbols: {symbols_str}")
    else:
        print(f"  Running: {Fore.RED}No{Style.RESET_ALL}")

def print_positions():
    """Print open positions"""
    status_data = read_status_file()
    positions = status_data.get('positions', []) if status_data else []
    
    print(f"\n{Fore.CYAN}Positions:{Style.RESET_ALL}")
    if not positions:
        print("  No open positions")
        return
    
    print(f"  {'Symbol':<10} {'Side':<6} {'Size':<10} {'Entry':<10} {'Current':<10} {'PnL':<10} {'ROI':<8}")
    print("  " + "-" * 70)
    
    for pos in positions:
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
        
        # Format with colors
        side_color = Fore.GREEN if side == 'Buy' else Fore.RED
        pnl_color = Fore.GREEN if float(pnl) >= 0 else Fore.RED
        roi_color = Fore.GREEN if roi >= 0 else Fore.RED
        
        print(f"  {symbol:<10} {side_color}{side:<6}{Style.RESET_ALL} {size:<10} {entry:<10} {current:<10} "
              f"{pnl_color}{pnl:<10}{Style.RESET_ALL} {roi_color}{roi:.2f}%{Style.RESET_ALL}")

def print_orders():
    """Print open orders"""
    status_data = read_status_file()
    orders = status_data.get('orders', []) if status_data else []
    
    print(f"\n{Fore.CYAN}Orders:{Style.RESET_ALL}")
    if not orders:
        print("  No open orders")
        return
    
    print(f"  {'Symbol':<10} {'Type':<6} {'Side':<6} {'Size':<10} {'Price':<10} {'Status':<10} {'Time':<10}")
    print("  " + "-" * 70)
    
    for order in orders:
        symbol = order.get('symbol', 'N/A')
        type_ = order.get('orderType', 'N/A')
        side = order.get('side', 'N/A')
        size = order.get('qty', '0')
        price = order.get('price', '0')
        status = order.get('orderStatus', 'N/A')
        
        # Convert timestamp to readable format
        try:
            time_str = datetime.fromtimestamp(int(order.get('createdTime', 0))/1000).strftime('%H:%M:%S')
        except:
            time_str = 'N/A'
        
        # Format with colors
        side_color = Fore.GREEN if side == 'Buy' else Fore.RED
        
        print(f"  {symbol:<10} {type_:<6} {side_color}{side:<6}{Style.RESET_ALL} {size:<10} {price:<10} "
              f"{status:<10} {time_str:<10}")

def print_performance():
    """Print performance metrics"""
    status_data = read_status_file()
    performance = status_data.get('performance', {}) if status_data else {}
    
    print(f"\n{Fore.CYAN}Performance:{Style.RESET_ALL}")
    if not performance:
        print("  No performance data available")
        return
    
    print(f"  Signals Generated: {performance.get('signals_generated', 0)}")
    print(f"  Orders Placed: {performance.get('orders_placed', 0)}")
    print(f"  Orders Filled: {performance.get('orders_filled', 0)}")
    
    errors = performance.get('errors', 0)
    error_color = Fore.GREEN if errors == 0 else Fore.RED
    print(f"  Errors: {error_color}{errors}{Style.RESET_ALL}")

def print_logs():
    """Print recent logs"""
    log_lines = read_log_lines(max_lines=10)
    
    print(f"\n{Fore.CYAN}Recent Logs:{Style.RESET_ALL}")
    if not log_lines:
        print("  No logs available")
        return
    
    for line in log_lines:
        line = line.strip()
        if "ERROR" in line:
            print(f"  {Fore.RED}{line}{Style.RESET_ALL}")
        elif "WARNING" in line:
            print(f"  {Fore.YELLOW}{line}{Style.RESET_ALL}")
        elif "INFO" in line:
            print(f"  {Fore.CYAN}{line}{Style.RESET_ALL}")
        else:
            print(f"  {line}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="PyBit Bot Simple Monitor")
    parser.add_argument("--refresh", "-r", type=int, default=5, help="Refresh rate in seconds")
    args = parser.parse_args()
    
    try:
        while True:
            clear_screen()
            print_header()
            print_status()
            print_positions()
            print_orders()
            print_performance()
            print_logs()
            
            print(f"\n{Fore.YELLOW}Press Ctrl+C to exit{Style.RESET_ALL}")
            time.sleep(args.refresh)
    except KeyboardInterrupt:
        print("\nExiting monitor...")

if __name__ == "__main__":
    main()