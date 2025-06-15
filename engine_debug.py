"""
Simple script to add DEBUG print statements to engine.py
"""
import os

def add_debug_prints():
    engine_path = "pybit_bot/engine.py"
    
    # Read original file
    with open(engine_path, 'r') as f:
        lines = f.readlines()
    
    # Create backup
    with open(f"{engine_path}.backup", 'w') as f:
        f.writelines(lines)
    
    # Find the main loop
    main_loop_found = False
    new_lines = []
    
    for line in lines:
        new_lines.append(line)
        
        # After defining the main loop method
        if "def _run_trading_loop" in line:
            new_lines.append("        # Debug prints added\n")
            new_lines.append("        import datetime\n")
            
        # Inside the main loop while statement
        if not main_loop_found and "while" in line and "_running" in line:
            main_loop_found = True
            indent = line.split("while")[0]
            new_lines.append(f"{indent}    # Debug output\n")
            new_lines.append(f"{indent}    print(f\"[{{datetime.datetime.now().strftime('%H:%M:%S')}}] Trading cycle active\")\n")
            
        # After fetching klines
        if "fetch_klines" in line and "=" in line:
            indent = line.split("=")[0]
            new_lines.append(f"{indent}print(f\"Fetched klines for {{symbol}}\")\n")
            
        # After computing indicators
        if any(ind in line for ind in ["luxfvgtrend", "tva", "cvd", "vfi", "atr"]) and "=" in line:
            indent = line.split("=")[0]
            new_lines.append(f"{indent}print(f\"Indicator calculated\")\n")
            
        # After generating signals
        if "generate_signals" in line:
            indent = line.split("generate_signals")[0]
            new_lines.append(f"{indent}print(f\"Checking for signals...\")\n")
    
    # Write modified file
    with open(engine_path, 'w') as f:
        f.writelines(new_lines)
    
    print("Added simple debug prints to engine.py")
    return True

if __name__ == "__main__":
    add_debug_prints()