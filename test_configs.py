#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os

def test_configs():
    """Test that all configuration files can be loaded correctly."""
    print("Testing new config structure...")
    
    # List of config files to test
    configs = ["general.json", "indicators.json", "execution.json", "strategy.json"]
    
    # Make sure the configs directory exists
    configs_dir = "pybit_bot/configs"
    if not os.path.exists(configs_dir):
        os.makedirs(configs_dir, exist_ok=True)
        print(f"Created configs directory: {configs_dir}")
    
    # Test each config file
    success = True
    for config_file in configs:
        path = os.path.join(configs_dir, config_file)
        print(f"Testing {path}...")
        
        try:
            with open(path, "r") as f:
                json.load(f)
            print(f"✓ Successfully loaded {config_file}")
        except FileNotFoundError:
            print(f"✗ ERROR: {config_file} not found")
            success = False
        except json.JSONDecodeError as e:
            print(f"✗ ERROR: {config_file} contains invalid JSON: {str(e)}")
            success = False
        except Exception as e:
            print(f"✗ ERROR: Failed to load {config_file}: {str(e)}")
            success = False
    
    if success:
        print("\nAll configs loaded successfully!")
    else:
        print("\nSome configs failed to load. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    test_configs()