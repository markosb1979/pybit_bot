"""
Enhance engine.py with detailed operational logging
"""
import os
import re
import sys

def enhance_engine_logging():
    """Add detailed operational logging to engine.py"""
    # Target the main engine file
    engine_path = "pybit_bot/engine.py"
    
    if not os.path.exists(engine_path):
        print(f"ERROR: Engine file not found at {engine_path}")
        return False
    
    try:
        # Read engine file
        with open(engine_path, 'r') as f:
            content = f.read()
        
        # Backup
        backup_path = f"{engine_path}.backup.{int(time.time())}"
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"Created backup at: {backup_path}")
        
        # Find the main loop in the engine
        if "def _run_trading_loop" in content:
            # Enhanced logging inside the trading loop
            loop_pattern = r"def _run_trading_loop\(self[^{]*?:(.*?)(?:def|\Z)"
            loop_match = re.search(loop_pattern, content, re.DOTALL)
            
            if loop_match:
                loop_content = loop_match.group(1)
                
                # Check if there's a while loop
                while_pattern = r"(\s+while\s+.*?:.*?(?=\n\s*(?:\S)))"
                while_match = re.search(while_pattern, loop_content, re.DOTALL)
                
                if while_match:
                    while_block = while_match.group(1)
                    indentation = re.match(r"(\s+)", while_block).group(1)
                    
                    # Add logging inside the while loop
                    enhanced_while_block = while_block + f"\n{indentation}    # Log current state\n" + \
                        f"{indentation}    self.logger.debug(f\"Market price: {{self._get_current_price()}}\")\n" + \
                        f"{indentation}    self.logger.debug(f\"Current positions: {{len(self.get_positions())}}\")\n" + \
                        f"{indentation}    self.logger.debug(f\"Strategy state: {{self.strategy.get_state() if hasattr(self.strategy, 'get_state') else 'Unknown'}}\")\n" + \
                        f"{indentation}    self.logger.debug(\"Trading cycle completed\")\n" + \
                        f"{indentation}    # Print to console\n" + \
                        f"{indentation}    if self._cycle_count % 10 == 0:  # Only print every 10 cycles\n" + \
                        f"{indentation}        print(f\"[{{datetime.now().strftime('%H:%M:%S')}}] Running - Price: {{self._get_current_price()}}, Positions: {{len(self.get_positions())}}\")\n"
                    
                    # Add cycle counter to __init__
                    init_pattern = r"def __init__\(self.*?\):(.*?)(?:def|\Z)"
                    init_match = re.search(init_pattern, content, re.DOTALL)
                    
                    if init_match:
                        init_content = init_match.group(1)
                        init_lines = init_content.split('\n')
                        last_line_index = 0
                        for i, line in enumerate(init_lines):
                            if line.strip() and i > last_line_index:
                                last_line_index = i
                        
                        indentation = re.match(r"(\s+)", init_lines[last_line_index]).group(1)
                        init_lines.insert(last_line_index + 1, f"{indentation}self._cycle_count = 0")
                        new_init_content = '\n'.join(init_lines)
                        
                        # Update init in content
                        content = content.replace(init_content, new_init_content)
                    
                    # Update cycle counter in while loop
                    if "self._cycle_count" not in enhanced_while_block:
                        enhanced_while_block += f"\n{indentation}    self._cycle_count += 1"
                    
                    # Replace in content
                    content = content.replace(while_block, enhanced_while_block)
        
        # Set default log level to DEBUG
        content = content.replace("root_logger.setLevel(logging.DEBUG)", "root_logger.setLevel(logging.DEBUG)")
        
        # Write modified content
        with open(engine_path, 'w') as f:
            f.write(content)
        
        print("Added detailed operational logging to engine.py")
        print("Please restart the bot to apply changes.")
        return True
        
    except Exception as e:
        print(f"Error enhancing engine logging: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import time
    enhance_engine_logging()