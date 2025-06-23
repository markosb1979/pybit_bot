"""
Debug script to locate and load configuration files
"""

import os
import glob
import json
import sys

def find_configs():
    """Find all possible config locations and report their contents"""
    print("\n=== CONFIG FINDER DIAGNOSTIC TOOL ===\n")
    
    # Get the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Script directory: {script_dir}")
    
    # Try various possible config locations
    possible_dirs = [
        # Current directory
        os.getcwd(),
        # Script directory
        script_dir,
        # Parent directory (project root)
        os.path.dirname(script_dir),
        # pybit_bot/configs within the project
        os.path.join(os.path.dirname(script_dir), "pybit_bot", "configs"),
        # configs within the current directory
        os.path.join(os.getcwd(), "configs"),
        # Remove config.json if present in path
        os.path.dirname(os.path.join(os.getcwd(), "pybit_bot", "configs", "config.json"))
    ]
    
    # The specific path mentioned in the error
    error_path = r"C:\Users\marko\OneDrive - Swinburne University\Documents\bybit_bot\pybit_bot\configs\config.json"
    error_dir = os.path.dirname(error_path)
    possible_dirs.append(error_dir)
    
    # Check each potential directory
    found_configs = False
    for config_dir in possible_dirs:
        print(f"\nChecking directory: {config_dir}")
        
        if not os.path.exists(config_dir):
            print(f"  - Directory does not exist")
            continue
            
        # Check what files exist in this directory
        files = os.listdir(config_dir)
        json_files = [f for f in files if f.endswith('.json')]
        print(f"  - Files in directory: {files}")
        print(f"  - JSON files found: {json_files}")
        
        # Check for our specific config files
        required_files = ['general.json', 'indicators.json', 'strategy.json', 'execution.json']
        found_required = [f for f in required_files if f in json_files]
        
        if found_required:
            print(f"  - Found required config files: {found_required}")
            print(f"  - Missing config files: {[f for f in required_files if f not in found_required]}")
            found_configs = True
            
            # Try to load one of the files to verify
            if 'general.json' in found_required:
                try:
                    with open(os.path.join(config_dir, 'general.json'), 'r') as f:
                        data = json.load(f)
                    print(f"  - Successfully loaded general.json")
                    # Print a sample of the data
                    if 'trading' in data:
                        print(f"  - Sample config data: 'trading.symbols' = {data['trading'].get('symbols')}")
                except Exception as e:
                    print(f"  - Error loading general.json: {str(e)}")
            
            print(f"\n*** RECOMMENDED CONFIG DIRECTORY: {config_dir} ***")
    
    if not found_configs:
        print("\nNo config files found in any expected location!")
        print("Please ensure the four required JSON files exist in one of these directories.")
        
    return found_configs

if __name__ == "__main__":
    found = find_configs()
    if found:
        print("\nConfig files were found. Use the recommended directory in your ConfigLoader.")
    else:
        print("\nNo config files found. Please check file locations and permissions.")