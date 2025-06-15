"""
Add explicit console logging to engine
"""
import os
import re
import sys

def add_console_logging():
    """Add console logging to engine.py"""
    # Try to find engine.py in common locations
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
        print("ERROR: Could not find engine.py automatically.")
        # Ask user for path
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
        
        # Backup
        with open(f"{engine_path}.backup", 'w') as f:
            f.write(content)
        print(f"Created backup at: {engine_path}.backup")
        
        # Add debug statements at key points
        modified_content = content
        
        # Add console handler import
        if "import logging" not in modified_content:
            import_section_end = modified_content.find("\n\n", modified_content.find("import"))
            if import_section_end > 0:
                modified_content = modified_content[:import_section_end] + "\nimport logging" + modified_content[import_section_end:]
        
        # Add console logging to initialization
        if "def __init__" in modified_content:
            init_method = modified_content.find("def __init__")
            method_body_start = modified_content.find(":", init_method) + 1
            next_line_pos = modified_content.find("\n", method_body_start) + 1
            
            console_logging = "\n        # Add console handler for debugging\n" + \
                             "        console = logging.StreamHandler()\n" + \
                             "        console.setLevel(logging.DEBUG)\n" + \
                             "        formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')\n" + \
                             "        console.setFormatter(formatter)\n" + \
                             "        logging.getLogger('').addHandler(console)\n" + \
                             "        print('Added console logging to engine')\n"
            
            modified_content = modified_content[:next_line_pos] + console_logging + modified_content[next_line_pos:]
        
        # Add debug log to start method
        if "def start" in modified_content:
            start_pos = modified_content.find("def start")
            method_body_start = modified_content.find(":", start_pos) + 1
            next_line_pos = modified_content.find("\n", method_body_start) + 1
            
            debug_log = "\n        print('Starting trading engine...')\n" + \
                       "        if hasattr(self, 'logger') and self.logger:\n" + \
                       "            self.logger.debug('Starting trading engine with detailed logging')\n" + \
                       "        else:\n" + \
                       "            print('WARNING: Logger not initialized')\n\n" + \
                       "        try:\n"
            
            end_method_pattern = r"return (True|False)"
            end_method_match = re.search(end_method_pattern, modified_content[start_pos:])
            if end_method_match:
                end_pos = start_pos + end_method_match.start()
                try_except = "\n        except Exception as e:\n" + \
                           "            print(f'ERROR starting engine: {str(e)}')\n" + \
                           "            import traceback\n" + \
                           "            traceback.print_exc()\n" + \
                           "            if hasattr(self, 'logger') and self.logger:\n" + \
                           "                self.logger.error(f'Error starting engine: {str(e)}')\n" + \
                           "            return False\n        "
                
                modified_content = modified_content[:next_line_pos] + debug_log + modified_content[next_line_pos:end_pos] + try_except + modified_content[end_pos:]
        
        # Write modified content
        with open(engine_path, 'w') as f:
            f.write(modified_content)
        
        print("Added console logging to engine. Restart the bot to apply changes.")
        return True
    
    except Exception as e:
        print(f"Error modifying engine: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    add_console_logging()