def print_init_imports():
    """Print the import statements in __init__.py"""
    try:
        with open('pybit_bot/__init__.py', 'r') as f:
            content = f.read()
            print("Contents of __init__.py:")
            print("------------------------")
            print(content)
    except Exception as e:
        print(f"Error reading __init__.py: {e}")

if __name__ == "__main__":
    print_init_imports()