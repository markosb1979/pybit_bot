"""
Enable debug mode for PyBit Bot
"""
import os
import json
import sys

def enable_debug():
    """Enable debug mode in config"""
    config_path = os.path.join("pybit_bot", "configs", "config.json")
    
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        return False
    
    try:
        # Load config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Backup original
        backup_path = f"{config_path}.backup"
        with open(backup_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Update log level
        if 'system' in config:
            config['system']['log_level'] = "DEBUG"
        else:
            config['system'] = {'log_level': "DEBUG"}
        
        # Save updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("Debug mode enabled. Log level set to DEBUG.")
        print("Restart the bot to apply changes.")
        return True
    
    except Exception as e:
        print(f"Error updating config: {e}")
        return False

if __name__ == "__main__":
    enable_debug()