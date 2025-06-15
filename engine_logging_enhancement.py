"""
Script to enhance PyBit Bot's engine.py with detailed operational logging
"""
import os
import re
import time
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
        
        # Backup original file
        backup_path = f"{engine_path}.bak.{int(time.time())}"
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"Created backup at: {backup_path}")
        
        # Add logging setup to ensure DEBUG level is used
        if "def __init__" in content:
            init_pattern = r"(def __init__.*?:.*?self\.logger\s*=\s*logging\.getLogger.*?\))"
            replacement = r"\1\n        self.logger.setLevel(logging.DEBUG)"
            content = re.sub(init_pattern, replacement, content, flags=re.DOTALL)
            print("Enhanced logger initialization")
        
        # Find the main trading loop
        if "_run_trading_loop" in content:
            # Add detailed logging inside the loop
            loop_pattern = r"(def _run_trading_loop.*?while\s+.*?:)"
            loop_replacement = r"\1\n            # Debug operational logging\n            self.logger.debug(f\"Trading cycle executing - Symbol: {self.config['trading']['symbol']}, Timeframe: {self.config['trading']['timeframe']}\")"
            content = re.sub(loop_pattern, loop_replacement, content, flags=re.DOTALL)
            print("Added operational cycle logging")
        
        # Add kline logging
        if "fetch_klines" in content or "get_klines" in content:
            # Find kline fetching methods
            kline_pattern = r"(def (?:fetch|get)_klines.*?return.*?)"
            kline_replacement = r"\1\n        self.logger.debug(f\"Fetched {len(klines) if 'klines' in locals() else 'unknown'} {timeframe} klines for {symbol}\")\n        if self.config.get('logging', {}).get('show_klines', False):\n            self.logger.debug(f\"Last kline: {klines[-1] if 'klines' in locals() and klines else 'None'}\")"
            content = re.sub(kline_pattern, kline_replacement, content, flags=re.DOTALL)
            print("Added kline logging")
        
        # Add indicator logging
        indicator_pattern = r"((?:luxfvgtrend|tva|cvd|vfi|atr).*?=.*?(?:calculate|compute).*?)"
        indicator_replacement = r"\1\n        self.logger.debug(f\"Indicator calculated: {name if 'name' in locals() else indicator_name} = {value if 'value' in locals() else result}\")"
        content = re.sub(indicator_pattern, indicator_replacement, content, flags=re.DOTALL)
        print("Added indicator logging")
        
        # Add signal generation logging
        signal_pattern = r"(def (?:generate|check)_signals.*?(?:return|yield).*?)"
        signal_replacement = r"\1\n        self.logger.debug(f\"Signal check completed: {signal if 'signal' in locals() else 'No signal'} for {symbol if 'symbol' in locals() else self.config['trading']['symbol']}\")\n        if 'signal' in locals() and signal and self.config.get('logging', {}).get('show_signals', False):\n            print(f\"[{datetime.datetime.now().strftime('%H:%M:%S')}] SIGNAL GENERATED: {signal}\")"
        content = re.sub(signal_pattern, signal_replacement, content, flags=re.DOTALL)
        print("Added signal logging")
        
        # Add periodic console output for activity verification
        loop_body_pattern = r"(while\s+.*?:.*?(?:time\.sleep|await asyncio\.sleep))"
        console_output = r"\1\n            # Periodic console output\n            if not hasattr(self, '_log_counter'):\n                self._log_counter = 0\n            self._log_counter += 1\n            if self._log_counter % 10 == 0:  # Every 10 cycles\n                import datetime\n                current_price = self._get_current_price() if hasattr(self, '_get_current_price') else 'Unknown'\n                positions = len(self.get_positions()) if hasattr(self, 'get_positions') else 'Unknown'\n                print(f\"[{datetime.datetime.now().strftime('%H:%M:%S')}] Bot active - Price: {current_price}, Positions: {positions}\")"
        content = re.sub(loop_body_pattern, console_output, content, flags=re.DOTALL)
        print("Added periodic console output")
        
        # Write modified content
        with open(engine_path, 'w') as f:
            f.write(content)
        
        print("\n✅ Successfully enhanced engine.py with detailed operational logging.")
        print("✅ Restart your bot to see the improved logging output.")
        return True
        
    except Exception as e:
        print(f"Error enhancing engine logging: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    enhance_engine_logging()