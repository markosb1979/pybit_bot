"""
Basic command implementations for PyBit Bot CLI
"""
import os
import sys
import json
import time
import signal
import subprocess
import psutil
import shutil
from pathlib import Path
from datetime import datetime

# Ensure we can import from parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from pybit_bot.engine import TradingEngine

# Constants
BOT_DIR = os.path.join(os.path.expanduser("~"), ".pybit_bot")
PID_FILE = os.path.join(BOT_DIR, "pybit_bot.pid")
STATUS_FILE = os.path.join(BOT_DIR, "status.json")
CONFIG_DIR = os.path.join(BOT_DIR, "config")

# Repository locations
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REPO_CONFIG_DIR = os.path.join(REPO_ROOT, "pybit_bot", "configs")

def _ensure_dirs_exist():
    """Ensure necessary directories exist"""
    os.makedirs(BOT_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(os.path.join(BOT_DIR, "logs"), exist_ok=True)

def _is_bot_running():
    """Check if the bot is running by checking PID file"""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        # Read PID from file
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        process = psutil.Process(pid)
        return process.is_running() and "python" in process.name().lower()
    except (ProcessLookupError, psutil.NoSuchProcess):
        # Process doesn't exist
        os.remove(PID_FILE)  # Clean up stale PID file
        return False
    except Exception as e:
        print(f"Error checking bot status: {str(e)}")
        return False

def _copy_repo_configs():
    """Copy configuration files from repository to user directory"""
    if not os.path.exists(REPO_CONFIG_DIR):
        print(f"Warning: Repository config directory not found: {REPO_CONFIG_DIR}")
        return False
    
    # Check if we have configs in the repository
    repo_config_files = [f for f in os.listdir(REPO_CONFIG_DIR) if f.endswith('.json')]
    if not repo_config_files:
        print(f"Warning: No configuration files found in repository: {REPO_CONFIG_DIR}")
        return False
    
    # Copy configs to user directory
    print(f"Copying {len(repo_config_files)} configuration files to {CONFIG_DIR}")
    for config_file in repo_config_files:
        src_path = os.path.join(REPO_CONFIG_DIR, config_file)
        dst_path = os.path.join(CONFIG_DIR, config_file)
        shutil.copy2(src_path, dst_path)
        print(f"Copied: {config_file}")
    
    return True

def _get_valid_config_path(args, logger):
    """Determine a valid configuration path"""
    # If user specified a path and it exists, use it
    if args.config and os.path.exists(args.config):
        return args.config
    
    # Check if default config dir has config files
    if os.path.exists(CONFIG_DIR):
        config_files = [f for f in os.listdir(CONFIG_DIR) if f.endswith('.json')]
        if config_files:
            return CONFIG_DIR
    
    # Check if repo config dir exists and has config files
    if os.path.exists(REPO_CONFIG_DIR):
        config_files = [f for f in os.listdir(REPO_CONFIG_DIR) if f.endswith('.json')]
        if config_files:
            logger.info(f"Using repository config directory: {REPO_CONFIG_DIR}")
            print(f"Using repository config directory: {REPO_CONFIG_DIR}")
            return REPO_CONFIG_DIR
    
    # Try to copy configs from repo to user dir
    if _copy_repo_configs():
        return CONFIG_DIR
    
    # No valid config path found
    logger.error("No valid configuration directory found")
    print("Error: No valid configuration directory found")
    return None

def start_command(args, logger):
    """Start the trading bot"""
    # Ensure directories exist
    _ensure_dirs_exist()
    
    # Check if bot is already running
    if _is_bot_running():
        logger.warning("Bot is already running")
        print("Error: Bot is already running. Use 'stop' to stop the bot first.")
        return False
    
    # Determine config path
    config_path = _get_valid_config_path(args, logger)
    if not config_path:
        return False
    
    logger.info(f"Using config from: {config_path}")
    print(f"Using config from: {config_path}")
    
    if args.daemon:
        # Start bot as daemon
        logger.info(f"Starting bot as daemon using config: {config_path}")
        print(f"Starting bot as daemon using config: {config_path}")
        
        # Construct the command
        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), "..", "daemon.py"),
            "--config", config_path
        ]
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Wait a moment to ensure process started
        time.sleep(2)
        
        if process.poll() is None:
            logger.info(f"Bot started as daemon with PID: {process.pid}")
            print(f"Bot started as daemon with PID: {process.pid}")
            
            # Save PID to file
            with open(PID_FILE, 'w') as f:
                f.write(str(process.pid))
            
            return True
        else:
            # Process failed to start
            stdout, stderr = process.communicate()
            logger.error(f"Failed to start bot: {stderr.decode()}")
            print(f"Error: Failed to start bot: {stderr.decode()}")
            return False
    else:
        # Start bot in current process
        logger.info(f"Starting bot in current process using config: {config_path}")
        print(f"Starting bot in current process using config: {config_path}")
        
        try:
            # Initialize the engine
            engine = TradingEngine(config_path)
            
            # Initialize and start the engine
            if engine.initialize():
                if engine.start():
                    # Save PID to file
                    with open(PID_FILE, 'w') as f:
                        f.write(str(os.getpid()))
                    
                    logger.info("Bot started successfully")
                    print("Bot started successfully")
                    
                    # Enter main loop
                    try:
                        # Register signal handlers
                        signal.signal(signal.SIGINT, lambda sig, frame: engine.stop())
                        signal.signal(signal.SIGTERM, lambda sig, frame: engine.stop())
                        
                        # Keep process running
                        print("Press Ctrl+C to stop the bot")
                        while engine.is_running:
                            time.sleep(1)
                            
                            # Write status to file periodically
                            engine.write_status_file(STATUS_FILE)
                    except KeyboardInterrupt:
                        print("\nStopping bot...")
                    finally:
                        engine.stop()
                        
                        # Remove PID file
                        if os.path.exists(PID_FILE):
                            os.remove(PID_FILE)
                    
                    return True
                else:
                    logger.error("Failed to start engine")
                    print("Error: Failed to start engine")
            else:
                logger.error("Failed to initialize engine")
                print("Error: Failed to initialize engine")
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}")
            print(f"Error: {str(e)}")
        
        return False

def stop_command(args, logger):
    """Stop the trading bot"""
    if not _is_bot_running():
        logger.warning("Bot is not running")
        print("Bot is not running")
        return True
    
    try:
        # Read PID from file
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGTERM to process
        logger.info(f"Stopping bot (PID: {pid})")
        print(f"Stopping bot (PID: {pid})")
        
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to terminate
        max_wait = 10  # seconds
        wait_start = time.time()
        
        while time.time() - wait_start < max_wait:
            try:
                # Check if process exists
                process = psutil.Process(pid)
                if not process.is_running():
                    break
                time.sleep(0.5)
            except (ProcessLookupError, psutil.NoSuchProcess):
                # Process is gone
                break
        
        # Check if process is still running
        try:
            process = psutil.Process(pid)
            if process.is_running():
                logger.warning(f"Bot did not stop gracefully, sending SIGKILL")
                print("Bot did not stop gracefully, forcing termination...")
                os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, psutil.NoSuchProcess):
            pass
        
        # Remove PID file
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        
        logger.info("Bot stopped successfully")
        print("Bot stopped successfully")
        return True
    except Exception as e:
        logger.error(f"Error stopping bot: {str(e)}")
        print(f"Error stopping bot: {str(e)}")
        return False

def status_command(args, logger):
    """Show the status of the trading bot"""
    # Check if bot is running
    is_running = _is_bot_running()
    
    # Get status from status file if it exists
    status_data = None
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f:
                status_data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading status file: {str(e)}")
            print(f"Error reading status file: {str(e)}")
    
    # Display status
    print("\n=== PyBit Bot Status ===")
    print(f"Status: {'Running' if is_running else 'Stopped'}")
    
    if is_running:
        # Get PID
        with open(PID_FILE, 'r') as f:
            pid = f.read().strip()
        print(f"PID: {pid}")
    
    if status_data:
        # Display additional status info
        print("\n=== Engine Details ===")
        
        # Runtime
        if 'start_time' in status_data and status_data['start_time']:
            start_time = datetime.fromisoformat(status_data['start_time'])
            runtime = datetime.now() - start_time
            runtime_str = str(runtime).split('.')[0]  # Remove microseconds
            print(f"Runtime: {runtime_str}")
        
        # Symbols
        if 'symbols' in status_data:
            symbols = status_data.get('symbols', [])
            print(f"Symbols: {', '.join(symbols)}")
        
        # Timeframes
        if 'timeframes' in status_data:
            timeframes = status_data.get('timeframes', [])
            print(f"Timeframes: {', '.join(timeframes)}")
        
        # Active strategies
        if 'active_strategies' in status_data:
            active_strategies = status_data.get('active_strategies', [])
            print(f"Active Strategies: {', '.join(active_strategies)}")
        
        # Active positions
        if 'active_positions' in status_data:
            active_positions = status_data.get('active_positions', 0)
            print(f"Active Positions: {active_positions}")
        
        # Performance
        if 'performance' in status_data:
            performance = status_data.get('performance', {})
            print("\n=== Performance ===")
            print(f"Signals Generated: {performance.get('signals_generated', 0)}")
            print(f"Orders Placed: {performance.get('orders_placed', 0)}")
            print(f"Orders Filled: {performance.get('orders_filled', 0)}")
            print(f"Errors: {performance.get('errors', 0)}")
            
            # Calculate P&L
            profits = performance.get('profits', 0)
            losses = performance.get('losses', 0)
            total_pnl = profits - losses
            print(f"Total P&L: {total_pnl:.4f} USDT")
        
        # Last update
        if 'last_update' in status_data:
            last_update = datetime.fromisoformat(status_data['last_update'])
            last_update_str = last_update.strftime('%Y-%m-%d %H:%M:%S')
            print(f"\nLast Update: {last_update_str}")
    
    print("\nUse 'monitor' command for real-time dashboard")
    return True