"""
test_client_demo.py

Runs the client_demo.py script and reports status.
"""

import subprocess

def main():
    print("Launching client_demo.py for BybitClient tests...")
    result = subprocess.run(["python", "client_demo.py"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("Test script exited with error code:", result.returncode)
        print(result.stderr)
    else:
        print("Test completed successfully.")

if __name__ == "__main__":
    main()