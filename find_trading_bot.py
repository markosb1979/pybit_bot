"""
Script to find the actual trading bot class in the project
"""
import os
import re

def find_trading_bot_class():
    """
    Search through Python files to find the main trading bot class
    """
    bot_classes = []
    for root, dirs, files in os.walk('pybit_bot'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        # Look for class definitions that might be the trading bot
                        class_matches = re.findall(r'class\s+(\w+)(?:\(.*\))?:', content)
                        for class_name in class_matches:
                            if 'Bot' in class_name or 'Engine' in class_name or 'Trading' in class_name:
                                bot_classes.append((class_name, file_path))
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    
    print(f"Found {len(bot_classes)} potential trading bot classes:")
    for i, (cls, path) in enumerate(bot_classes, 1):
        print(f"{i}. {cls} in {path}")
    
    return bot_classes

if __name__ == "__main__":
    find_trading_bot_class()