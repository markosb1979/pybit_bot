# This script patches the incorrect import in trading_bot.py
import os
import fileinput
import sys

def patch_trading_bot():
    """
    Fixes the import in trading_bot.py from ..core.data_manager to ..managers.data_manager
    """
    file_path = os.path.join('pybit_bot', 'core', 'trading_bot.py')
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find {file_path}")
        return False
    
    # Read the file and check if the incorrect import exists
    found_import = False
    with open(file_path, 'r') as f:
        content = f.read()
        if 'from ..core.data_manager import DataManager' in content:
            found_import = True
    
    if not found_import:
        print("Import statement not found or already fixed.")
        return False
    
    # Replace the import
    with fileinput.FileInput(file_path, inplace=True) as file:
        for line in file:
            new_line = line.replace(
                'from ..core.data_manager import DataManager', 
                'from ..managers.data_manager import DataManager'
            )
            print(new_line, end='')
    
    print(f"Updated import in {file_path}")
    return True

if __name__ == "__main__":
    if patch_trading_bot():
        print("Successfully patched trading_bot.py")
    else:
        print("No changes made to trading_bot.py")