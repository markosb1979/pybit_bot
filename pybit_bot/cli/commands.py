"""
PyBit Bot CLI Command implementations
"""
import os
import sys
import json
import signal
import subprocess
import psutil
from datetime import datetime
import tempfile

# Constants
PID_FILE = os.path.join(os.path.expanduser("~"), ".pybit_bot", "pybit_bot.pid")
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs")

def _get_config_path(config_name):
    """Get the full path to a config file"""
    # Check if it's a direct path
    if os.path.exists(config_name):
        return config_name
    
    # Check in configs directory
    config_path = os.path.join(CONFIG_DIR, config_name)
    if os.path.exists(config_path):
        return config_path
    
    # Check if it needs .json extension
    if not config_name.endswith('.json'):
        config_path = os.path.join(CONFIG_DIR, f"{config_name}.json")
        if os.path.exists(config_path):
            return config_path
    
    raise FileNotFoundError(f"Config file not found: {config_name}")

def _is_bot_running():
    """Check if the bot is currently running"""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        process = psutil.Process(pid)
        # Verify it's our bot process by checking command line
        cmdline = " ".join(process.cmdline()) if hasattr(process, 'cmdline') else ""
        if process.is_running() and "python" in process.name().lower() and "pybit_bot" in cmdline:
            return True
        else:
            # Not our process, remove the PID file
            os.remove(PID_FILE)
            return False
    except (ProcessLookupError, psutil.NoSuchProcess, FileNotFoundError):
        # Process no longer exists
        try:
            os.remove(PID_FILE)
        except:
            pass
        return False
    except Exception as e:
        print(f"Error checking if bot is running: {e}")
        return False

def start_command(args, logger):
    """Start the trading bot"""
    if _is_bot_running():
        logger.error("Bot is already running. Use 'stop' command first or 'status' to check.")
        return
    
    try:
        config_path = _get_config_path(args.config)
        logger.info(f"Starting bot with config: {config_path}")
        
        if args.daemon:
            # Start as daemon process
            cmd = [
                sys.executable, 
                "-m", "pybit_bot.cli.bot_runner", 
                "--config", config_path
            ]
            
            if args.testnet:
                cmd.append("--testnet")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Save PID
            os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
            with open(PID_FILE, 'w') as f:
                f.write(str(process.pid))
            
            logger.info(f"Bot started in daemon mode with PID: {process.pid}")
            
        else:
            # Start in foreground
            from pybit_bot.cli.bot_runner import run_bot
            run_bot(config_path, testnet=args.testnet)
    
    except FileNotFoundError as e:
        logger.error(f"Error: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")

def stop_command(args, logger):
    """Stop the trading bot"""
    if not _is_bot_running():
        logger.error("Bot is not running.")
        return
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGTERM to the process
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Sent stop signal to bot (PID: {pid})")
        
        # Remove PID file
        os.remove(PID_FILE)
    except Exception as e:
        logger.error(f"Failed to stop bot: {str(e)}")

def status_command(args, logger):
    """Show bot status"""
    if not _is_bot_running():
        print("Bot status: Not running")
        return
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        process = psutil.Process(pid)
        
        # Get start time
        start_time = datetime.fromtimestamp(process.create_time())
        uptime = datetime.now() - start_time
        
        # Get memory usage
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        print("\nBot Status:")
        print(f"  Running: Yes")
        print(f"  PID: {pid}")
        print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Uptime: {uptime}")
        print(f"  Memory: {memory_mb:.2f} MB")
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        print("Bot status: Error")

def positions_command(args, logger):
    """Show current positions"""
    if not _is_bot_running():
        logger.error("Bot is not running.")
        return
    
    # This would require IPC to get positions from the running bot
    # For now, we'll implement a simplified version that reads from a status file
    status_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "status.json")
    
    if not os.path.exists(status_file):
        print("No status information available.")
        return
    
    try:
        with open(status_file, 'r') as f:
            status = json.load(f)
        
        positions = status.get('positions', [])
        
        if not positions:
            print("No open positions.")
            return
        
        print("\nOpen Positions:")
        print(f"{'Symbol':<10} {'Side':<6} {'Size':<10} {'Entry':<10} {'Current':<10} {'PnL':<10} {'ROI':<8}")
        print("-" * 70)
        
        for pos in positions:
            symbol = pos.get('symbol', 'N/A')
            side = pos.get('side', 'N/A')
            size = pos.get('size', '0')
            entry = pos.get('entryPrice', '0')
            current = pos.get('markPrice', '0')
            pnl = pos.get('unrealisedPnl', '0')
            
            try:
                roi = (float(pnl) / (float(entry) * float(size))) * 100 if float(entry) > 0 and float(size) > 0 else 0
            except:
                roi = 0
            
            print(f"{symbol:<10} {side:<6} {size:<10} {entry:<10} {current:<10} {pnl:<10} {roi:.2f}%")
    
    except Exception as e:
        logger.error(f"Error reading positions: {str(e)}")
        print("Error retrieving position information.")

def orders_command(args, logger):
    """Show open orders"""
    if not _is_bot_running():
        logger.error("Bot is not running.")
        return
    
    # Similar to positions, we'll read from a status file
    status_file = os.path.join(os.path.expanduser("~"), ".pybit_bot", "status.json")
    
    if not os.path.exists(status_file):
        print("No status information available.")
        return
    
    try:
        with open(status_file, 'r') as f:
            status = json.load(f)
        
        orders = status.get('orders', [])
        
        if not orders:
            print("No open orders.")
            return
        
        print("\nOpen Orders:")
        print(f"{'Symbol':<10} {'Type':<6} {'Side':<6} {'Size':<10} {'Price':<10} {'Status':<10} {'Time':<10}")
        print("-" * 70)
        
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
            
            print(f"{symbol:<10} {type_:<6} {side:<6} {size:<10} {price:<10} {status:<10} {time_str:<10}")
    
    except Exception as e:
        logger.error(f"Error reading orders: {str(e)}")
        print("Error retrieving order information.")

def logs_command(args, logger):
    """Show log files"""
    log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
    
    if not os.path.exists(log_dir):
        print("No logs found.")
        return
    
    # Get list of log files
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
    log_files.sort(reverse=True)
    
    if not log_files:
        print("No log files found.")
        return
    
    # Show the most recent log file
    log_file = os.path.join(log_dir, log_files[0])
    
    try:
        # Use tail or equivalent to show the last N lines
        if sys.platform == 'win32':
            # Windows doesn't have tail, read the file ourselves
            with open(log_file, 'r') as f:
                lines = f.readlines()
                tail = lines[-args.lines:] if len(lines) > args.lines else lines
                for line in tail:
                    print(line.strip())
        else:
            # On Unix, use tail command
            cmd = ['tail', f'-n{args.lines}']
            if args.follow:
                cmd.append('-f')
            cmd.append(log_file)
            
            subprocess.run(cmd)
    
    except Exception as e:
        logger.error(f"Error reading logs: {str(e)}")
        print(f"Error reading log file: {str(e)}")

def config_command(args, logger):
    """View or edit configuration"""
    # List available config files
    config_files = [f for f in os.listdir(CONFIG_DIR) if f.endswith('.json')]
    
    if not config_files:
        print("No configuration files found.")
        return
    
    # Show available configs
    print("\nAvailable configurations:")
    for i, config_file in enumerate(config_files, 1):
        print(f"  {i}. {config_file}")
    
    # Prompt user to select a config
    try:
        selection = int(input("\nSelect a configuration (number): "))
        if selection < 1 or selection > len(config_files):
            print("Invalid selection.")
            return
        
        selected_config = config_files[selection-1]
        config_path = os.path.join(CONFIG_DIR, selected_config)
        
        # Load the config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if args.edit:
            # Create a temporary file with the config
            with tempfile.NamedTemporaryFile(suffix='.json', mode='w+', delete=False) as tmp:
                json.dump(config, tmp, indent=2)
                tmp_path = tmp.name
            
            # Open the file in the default editor
            if sys.platform == 'win32':
                os.startfile(tmp_path)
            else:
                editor = os.environ.get('EDITOR', 'nano')
                subprocess.call([editor, tmp_path])
            
            # Prompt to save changes
            save = input("Save changes? (y/n): ")
            if save.lower() == 'y':
                with open(tmp_path, 'r') as tmp:
                    new_config = json.load(tmp)
                
                with open(config_path, 'w') as f:
                    json.dump(new_config, f, indent=2)
                
                print(f"Configuration saved to {config_path}")
            
            # Clean up
            os.unlink(tmp_path)
        else:
            # Pretty print the config
            print(f"\nConfiguration: {selected_config}")
            print(json.dumps(config, indent=2))
    
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        logger.error(f"Error with configuration: {str(e)}")
        print(f"Error: {str(e)}")