#!/usr/bin/env python3
import os
import re
import sys
import ast

def find_manager_calls(base_dir):
    pattern = re.compile(r'self\.(client|order_client)\.')
    for root, _, files in os.walk(base_dir):
        rel = os.path.relpath(root, base_dir)
        # only core/ and managers/ directories
        if not (rel.startswith('core') or rel.startswith('managers')):
            continue
        for fname in files:
            if not fname.endswith('.py'):
                continue
            path = os.path.join(root, fname)
            for lineno, line in enumerate(open(path, encoding='utf-8'), start=1):
                if pattern.search(line):
                    print(f"{os.path.relpath(path, base_dir)}:{lineno}: {line.strip()}")

def list_public_methods(path):
    """
    Parse the file at `path` and return a sorted list of all
    FunctionDef names that do NOT start with an underscore.
    """
    try:
        source = open(path, encoding='utf-8').read()
        tree = ast.parse(source, filename=path)
    except Exception as e:
        return [f"# failed to parse {path}: {e}"]

    methods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not node.name.startswith('_'):
                methods.append(node.name)
    return sorted(set(methods))

def main():
    if len(sys.argv) != 2:
        print("Usage: python search_calls.py <base_dir>")
        sys.exit(1)
    base = sys.argv[1]

    print("=== Manager → Client Calls ===\n")
    find_manager_calls(base)

    print("\n=== Public methods in client.py and order_manager_client.py ===\n")
    for rel in ('core/client.py', 'core/order_manager_client.py'):
        full = os.path.join(base, rel)
        print(f"{rel}:")
        for m in list_public_methods(full):
            print(f"  - {m}")
        print()

if __name__ == '__main__':
    main()
