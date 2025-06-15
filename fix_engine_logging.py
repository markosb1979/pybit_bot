"""
Add detailed logging to the main PyBit Bot engine
"""
import os
import re
import sys

def add_engine_logging():
    """Add comprehensive logging to main engine.py"""
    # Target the main engine file specifically
    engine_path = "pybit_bot/engine.py"
    
    if not os.path.exists(engine_path):
        print(f"ERROR: Main engine file not found at {engine_path}")
        return False
    
    print(f"Found main engine file at: {engine_path}")
    
    try:
        # Read engine file
        with open(engine_path, 'r') as f:
            content = f.read()
        
        # Backup
        backup_path = f"{engine_path}.backup"
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"Created backup at: {backup_path}")
        
        # Add comprehensive logging and error handling
        modified_content = content
        
        # Add file logging and console logging setup
        if "def __init__" in modified_content:
            init_pos = modified_content.find("def __init__")
            init_body_start = modified_content.find(":", init_pos) + 1
            next_line_pos = modified_content.find("\n", init_body_start) + 1
            
            logging_setup = """
        # Enhanced logging setup
        import logging
        import sys
        import os
        
        # Ensure log directory exists
        log_dir = os.path.join(os.path.expanduser("~"), ".pybit_bot", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Create engine log file
        self.log_file = os.path.join(log_dir, "engine.log")
        
        # Configure root logger with console and file output
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Add console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
        console.setFormatter(console_formatter)
        root_logger.addHandler(console)
        
        # Add file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Direct output to console as well for visibility
        print(f"Engine initializing. Logs will be written to {self.log_file}")
        
"""
            modified_content = modified_content[:next_line_pos] + logging_setup + modified_content[next_line_pos:]
        
        # Write modified content
        with open(engine_path, 'w') as f:
            f.write(modified_content)
        
        print("Added comprehensive logging to engine file.")
        print("Please restart the bot to apply changes.")
        return True
        
    except Exception as e:
        print(f"Error modifying engine: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    add_engine_logging()