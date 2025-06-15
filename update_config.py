"""
Add direct print statements to engine methods
"""
import os
import re

def add_debug_prints():
    # Find engine file (same as previous script)
    potential_paths = [
        "pybit_bot/engine.py",
        "pybit_bot/core/engine.py",
        "pybit_bot/trading/engine.py"
    ]
    
    engine_path = None
    for path in potential_paths:
        if os.path.exists(path):
            engine_path = path
            break
    
    if not engine_path:
        user_path = input("Please enter the path to engine.py: ")
        if os.path.exists(user_path):
            engine_path = user_path
        else:
            print(f"File not found: {user_path}")
            return False
    
    print(f"Found engine file at: {engine_path}")
    
    try:
        # Read engine file
        with open(engine_path, 'r') as f:
            content = f.read()
        
        # Backup if not already backed up
        backup_path = f"{engine_path}.debug_backup"
        if not os.path.exists(backup_path):
            with open(backup_path, 'w') as f:
                f.write(content)
            print(f"Created backup at: {backup_path}")
        
        # Add print statements to every method
        modified_content = content
        method_pattern = r"def\s+(\w+)\s*\("
        
        for match in re.finditer(method_pattern, content):
            method_name = match.group(1)
            method_start = match.start()
            
            # Skip certain methods
            if method_name in ["__init__", "__str__", "__repr__"]:
                continue
                
            # Find method body start
            body_start = content.find(":", method_start)
            next_line = content.find("\n", body_start) + 1
            
            # Add print statement
            debug_print = f"\n        print('DEBUG: Engine.{method_name} called')\n"
            
            # Insert debug print after method start
            modified_content = modified_content[:next_line] + debug_print + modified_content[next_line:]
        
        # Write modified content
        with open(engine_path, 'w') as f:
            f.write(modified_content)
        
        print("Added debug prints to all engine methods. Restart the bot to apply changes.")
        return True
        
    except Exception as e:
        print(f"Error adding debug prints: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    add_debug_prints()