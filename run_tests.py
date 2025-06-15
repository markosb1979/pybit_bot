# run_tests.py - Place this in your project root
import os
import sys
import importlib.util
import glob
import asyncio

# Get all test files
test_files = glob.glob('tests/*.py')

# Run each test file
async def run_tests():
    for test_file in test_files:
        module_name = os.path.basename(test_file).replace('.py', '')
        print(f"\n{'='*50}\nRunning {module_name}\n{'='*50}")
        
        # Import the module
        spec = importlib.util.spec_from_file_location(module_name, test_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # If the module has a test_* function, run it
        test_func_name = f"test_{module_name.replace('_test', '')}"
        if hasattr(module, test_func_name):
            test_func = getattr(module, test_func_name)
            if callable(test_func):
                if asyncio.iscoroutinefunction(test_func):
                    await test_func()
                else:
                    test_func()
            else:
                print(f"Skipping {test_func_name} - not callable")
        else:
            print(f"Skipping {module_name} - no test function found")

if __name__ == "__main__":
    asyncio.run(run_tests())