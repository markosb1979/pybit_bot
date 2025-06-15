def fix_init_py():
    """Fix the syntax error in __init__.py by adding the missing closing parenthesis"""
    file_path = 'pybit_bot/__init__.py'
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check if there's a missing parenthesis
        if 'ConfigurationError\n\n' in content:
            # Add the missing parenthesis
            fixed_content = content.replace('ConfigurationError\n\n', 'ConfigurationError)\n\n')
            
            # Write the fixed content back to the file
            with open(file_path, 'w') as f:
                f.write(fixed_content)
            
            print(f"Fixed missing parenthesis in {file_path}")
            return True
        else:
            print("No syntax error found or pattern doesn't match. Manual fix might be needed.")
            return False
            
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

if __name__ == "__main__":
    fix_init_py()