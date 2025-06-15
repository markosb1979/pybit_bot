"""
Add detailed logging to the main PyBit Bot engine
"""
import os
import re
import sys

def add_engine_logging():
    """Add comprehensive logging to main engine.py"""
    # Target the main engine file specifically
    engine_path = "pybit_bot/pybit_bot/engine.py"
    
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
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
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
        
        # Add detailed debug logging to start method
        if "def start" in modified_content:
            start_pos = modified_content.find("def start")
            start_body_start = modified_content.find(":", start_pos) + 1
            next_line_pos = modified_content.find("\n", start_body_start) + 1
            
            start_logging = """
        # Comprehensive startup logging
        print("TRADING ENGINE STARTING...")
        import traceback
        
        if hasattr(self, 'logger') and self.logger:
            self.logger.debug("Trading engine starting with detailed logging")
        else:
            print("WARNING: Logger not properly initialized")
            import logging
            self.logger = logging.getLogger("TradingEngine")
        
        try:
            # Log configuration
            if hasattr(self, 'config') and self.config:
                self.logger.debug(f"Configuration: {self.config}")
            else:
                self.logger.warning("No configuration available")
        
"""
            # Find the end of the method to add exception handling
            method_end_pattern = r"return (True|False)"
            method_end_match = re.search(method_end_pattern, modified_content[start_pos:])
            
            if method_end_match:
                end_pos = start_pos + method_end_match.start()
                
                exception_handling = """
        except Exception as e:
            error_msg = f"CRITICAL ERROR starting engine: {str(e)}"
            print(error_msg)
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(error_msg)
                self.logger.error(traceback.format_exc())
            return False
            
"""
                modified_content = modified_content[:next_line_pos] + start_logging + modified_content[next_line_pos:end_pos] + exception_handling + modified_content[end_pos:]
        
        # Add logging to key methods
        key_methods = ["_initialize_components", "_start_market_data", "_run_trading_loop", "stop"]
        
        for method in key_methods:
            method_pattern = rf"def\s+{method}\s*\("
            method_match = re.search(method_pattern, modified_content)
            
            if method_match:
                method_pos = method_match.start()
                method_body_start = modified_content.find(":", method_pos) + 1
                next_line_pos = modified_content.find("\n", method_body_start) + 1
                
                method_logging = f"""
        # Debug logging for {method}
        self.logger.debug("Executing {method}")
        
        try:
"""
                # Find the end of the method to add exception handling
                next_method_match = re.search(r"def\s+\w+\s*\(", modified_content[next_line_pos:])
                if next_method_match:
                    method_end = next_line_pos + next_method_match.start()
                    
                    # Check if there's a return statement
                    return_match = re.search(r"return", modified_content[next_line_pos:method_end])
                    if return_match:
                        return_pos = next_line_pos + return_match.start()
                        
                        # Add indentation to any return statements
                        return_block = modified_content[return_pos:method_end]
                        indented_return = return_block.replace("return", "        return")
                        
                        exception_handling = """
        except Exception as e:
            error_msg = f"Error in {method}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            return None
            
"""
                        modified_content = modified_content[:next_line_pos] + method_logging + \
                                        modified_content[next_line_pos:return_pos] + \
                                        indented_return + exception_handling + \
                                        modified_content[method_end:]
        
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