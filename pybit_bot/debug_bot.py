"""
PyBit Bot Debug Helper
"""
import os
import sys
import json
import time
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pybit_bot.core.client import BybitClient, APICredentials
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_api_connection():
    """Test API connection"""
    print("Testing Bybit API connection...")
    try:
        # Get credentials from environment
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
        testnet = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
        
        if not api_key or not api_secret:
            print("ERROR: API credentials not found in .env file")
            return False
        
        # Initialize client
        credentials = APICredentials(api_key, api_secret)
        client = BybitClient(credentials, testnet=testnet)
        
        # Test connection
        server_time = client.get_server_time()
        print(f"✓ Connected to Bybit {'Testnet' if testnet else 'Mainnet'}")
        print(f"✓ Server time: {server_time}")
        
        # Get account info
        account = client.get_wallet_balance()
        print(f"✓ Account balance: {account}")
        
        # Get market data
        klines = client.get_klines("BTCUSDT", "1m", limit=5)
        print(f"✓ Market data received: {len(klines)} candles")
        
        return True
    except Exception as e:
        print(f"✗ API connection error: {str(e)}")
        return False

def check_bot_status():
    """Check bot status"""
    print("\nChecking bot status...")
    
    # Check PID file
    pid_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "pybit_bot.pid")
    if not os.path.exists(pid_file):
        print("✗ Bot is not running (PID file not found)")
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check process
        import psutil
        try:
            process = psutil.Process(pid)
            if process.is_running():
                print(f"✓ Bot is running with PID: {pid}")
                print(f"✓ Started at: {datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"✓ Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
                
                # Check status file
                status_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "status.json")
                if os.path.exists(status_file):
                    with open(status_file, 'r') as f:
                        status = json.load(f)
                    
                    print(f"✓ Bot runtime: {status.get('runtime', 'N/A')}")
                    print(f"✓ Last update: {status.get('last_update', 'N/A')}")
                    print(f"✓ Symbols: {status.get('symbols', [])}")
                    print(f"✓ Performance: {json.dumps(status.get('performance', {}))}")
                
                return True
            else:
                print(f"✗ Process {pid} exists but is not running")
                return False
        except psutil.NoSuchProcess:
            print(f"✗ Process {pid} does not exist")
            return False
    except Exception as e:
        print(f"✗ Error checking bot status: {str(e)}")
        return False

def check_config():
    """Check bot configuration"""
    print("\nChecking bot configuration...")
    
    # Find config file
    config_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "pybit_bot", "configs"),
        "configs",
        "pybit_bot/configs"
    ]
    
    config_file = None
    for config_dir in config_dirs:
        test_path = os.path.join(config_dir, "config.json")
        if os.path.exists(test_path):
            config_file = test_path
            break
    
    if not config_file:
        print("✗ Config file not found")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        print(f"✓ Config file found: {config_file}")
        print(f"✓ Trading symbol: {config.get('trading', {}).get('symbol', 'N/A')}")
        print(f"✓ Timeframe: {config.get('trading', {}).get('timeframe', 'N/A')}")
        print(f"✓ Position size: {config.get('trading', {}).get('position_size_usdt', 'N/A')} USDT")
        print(f"✓ Max positions: {config.get('trading', {}).get('max_positions', 'N/A')}")
        
        # Check risk settings
        risk = config.get('risk', {})
        print(f"✓ Stop loss: {risk.get('stop_loss_pct', 'N/A') * 100}%")
        print(f"✓ Take profit: {risk.get('take_profit_pct', 'N/A') * 100}%")
        print(f"✓ Max daily loss: {risk.get('max_daily_loss_usdt', 'N/A')} USDT")
        
        return True
    except Exception as e:
        print(f"✗ Error reading config: {str(e)}")
        return False

def check_recent_logs():
    """Check recent log entries"""
    print("\nChecking recent logs...")
    
    log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
    if not os.path.exists(log_dir):
        print("✗ Log directory not found")
        return False
    
    # Get log files sorted by modification time (newest first)
    log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.log')]
    log_files.sort(key=os.path.getmtime, reverse=True)
    
    if not log_files:
        print("✗ No log files found")
        return False
    
    log_file = log_files[0]
    print(f"✓ Latest log file: {os.path.basename(log_file)}")
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            
        # Get the last 10 lines
        last_lines = lines[-10:]
        print("✓ Recent log entries:")
        for line in last_lines:
            print(f"  {line.strip()}")
            
        # Look for specific events
        errors = [line for line in lines[-50:] if "ERROR" in line]
        if errors:
            print("\n✗ Found errors in recent logs:")
            for error in errors[:5]:  # Show up to 5 errors
                print(f"  {error.strip()}")
        
        connections = [line for line in lines[-50:] if "connect" in line.lower() or "api" in line.lower()]
        if connections:
            print("\n✓ Found API/connection related entries:")
            for conn in connections[:5]:  # Show up to 5 connections
                print(f"  {conn.strip()}")
        
        return True
    except Exception as e:
        print(f"✗ Error reading logs: {str(e)}")
        return False

def main():
    """Main function"""
    print("=" * 80)
    print("PyBit Bot Diagnostic Tool")
    print("=" * 80)
    
    # Run checks
    api_ok = check_api_connection()
    status_ok = check_bot_status()
    config_ok = check_config()
    logs_ok = check_recent_logs()
    
    # Overall assessment
    print("\n" + "=" * 80)
    print("Diagnostic Summary:")
    print(f"API Connection: {'✓ OK' if api_ok else '✗ Issues detected'}")
    print(f"Bot Status: {'✓ OK' if status_ok else '✗ Issues detected'}")
    print(f"Configuration: {'✓ OK' if config_ok else '✗ Issues detected'}")
    print(f"Logs: {'✓ OK' if logs_ok else '✗ Issues detected'}")
    print("=" * 80)
    
    # Recommendations
    if not all([api_ok, status_ok, config_ok, logs_ok]):
        print("\nRecommended actions:")
        if not api_ok:
            print("- Check your .env file for correct API credentials")
            print("- Verify your Bybit account has API access enabled")
        if not status_ok:
            print("- Restart the bot using the CLI")
            print("- Check for error messages during startup")
        if not config_ok:
            print("- Verify your config.json file has correct settings")
            print("- Ensure trading symbol and position size are properly set")
        if not logs_ok:
            print("- Check log files for detailed error messages")
            print("- Increase log level to DEBUG for more information")

if __name__ == "__main__":
    main()