"""
PyBit Bot - Log Viewer Command
------------------------------
Command to view and follow bot logs
"""

import os
import time
import argparse
import sys
from datetime import datetime

def setup_parser(subparsers):
    """Setup parser for logs command"""
    parser = subparsers.add_parser('logs', help='View trading bot logs')
    parser.add_argument('--follow', '-f', action='store_true', help='Follow log output')
    parser.add_argument('--lines', '-n', type=int, default=50, help='Number of lines to show')
    parser.add_argument('--engine-only', action='store_true', help='Show only engine logs')
    parser.set_defaults(func=logs_command)
    
def logs_command(args):
    """Show bot logs"""
    # Get home directory path
    home_dir = os.path.expanduser('~')
    log_dir = os.path.join(home_dir, '.pybit_bot', 'logs')
    
    # Determine which log file to show
    if args.engine_only:
        log_files = ['engine.log']
    else:
        # Get all log files
        try:
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        except FileNotFoundError:
            print(f"Error: Log directory not found at {log_dir}")
            return False
    
    if not log_files:
        print("No log files found.")
        return False
    
    # Print header
    print(f"PyBit Bot Logs - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log directory: {log_dir}")
    print(f"Showing {args.lines} lines{' (follow mode)' if args.follow else ''}")
    print("-" * 80)
    
    # Function to display logs
    def display_logs():
        for log_file in log_files:
            log_path = os.path.join(log_dir, log_file)
            try:
                with open(log_path, 'r') as f:
                    # Get last N lines
                    lines = f.readlines()
                    if lines:
                        print(f"\n=== {log_file} ===\n")
                        for line in lines[-args.lines:]:
                            print(line.rstrip())
            except FileNotFoundError:
                print(f"Log file not found: {log_path}")
            except Exception as e:
                print(f"Error reading log file {log_path}: {str(e)}")
    
    # Display logs once
    display_logs()
    
    # If follow mode, continue to display new content
    if args.follow:
        print("\nWatching for new logs... (Ctrl+C to exit)")
        
        # Keep track of file sizes
        file_sizes = {}
        for log_file in log_files:
            log_path = os.path.join(log_dir, log_file)
            try:
                file_sizes[log_path] = os.path.getsize(log_path)
            except:
                file_sizes[log_path] = 0
        
        try:
            while True:
                time.sleep(0.5)  # Check every half second
                something_changed = False
                
                for log_file in log_files:
                    log_path = os.path.join(log_dir, log_file)
                    try:
                        current_size = os.path.getsize(log_path)
                        
                        # If file has grown
                        if current_size > file_sizes.get(log_path, 0):
                            with open(log_path, 'r') as f:
                                # Seek to previous position
                                f.seek(file_sizes.get(log_path, 0))
                                # Read new content
                                new_content = f.read()
                                if new_content:
                                    print(f"\n=== {log_file} ===\n")
                                    print(new_content, end='')
                                    something_changed = True
                            
                            # Update file size
                            file_sizes[log_path] = current_size
                    except:
                        continue
                        
                # If nothing changed, no need to print anything
                if not something_changed:
                    continue
                    
        except KeyboardInterrupt:
            print("\nLog following stopped.")
            return True
    
    return True