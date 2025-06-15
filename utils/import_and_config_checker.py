"""
import_and_config_checker.py

This script scans your Python project for:
- Broken or missing imports (modules, packages, files)
- Broken references to JSON config files
- General communication issues between scripts and config/data files

Usage:
    python import_and_config_checker.py /path/to/your/project

Output:
    - Lists missing imports and where they are used
    - Lists missing JSON config files referenced in code
    - Reports any import/JSON load errors statically and dynamically
"""

import os
import ast
import importlib.util
import sys
import glob
import json

from collections import defaultdict

def find_python_files(root_dir):
    py_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if fname.endswith('.py'):
                py_files.append(os.path.join(dirpath, fname))
    return py_files

def find_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        node = ast.parse(f.read(), filename=file_path)
    imports = []
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            for alias in n.names:
                imports.append(alias.name)
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                imports.append(n.module)
    return imports

def check_imports(py_files, project_root):
    missing_imports = defaultdict(list)
    for pyf in py_files:
        imports = find_imports(pyf)
        for imp in set(imports):
            # Try dynamic import (relative to project root if local, else system)
            try:
                if imp.startswith("pybit_bot") or imp.startswith("."):
                    # Try to resolve as local file/module
                    rel_path = os.path.join(project_root, *imp.split(".")) + ".py"
                    if not os.path.exists(rel_path) and not os.path.exists(os.path.join(project_root, *imp.split("."), "__init__.py")):
                        missing_imports[imp].append(pyf)
                else:
                    importlib.util.find_spec(imp)
            except Exception:
                missing_imports[imp].append(pyf)
    return missing_imports

def find_json_references(file_path):
    """Finds strings in open/load that look like JSON config references."""
    json_refs = set()
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        # Look for json.load(open("...")) or open("...json")
        if "json.load" in line or ".json" in line or "open(" in line:
            parts = line.split("open(")
            for part in parts[1:]:
                quote = '"' if '"' in part else "'"
                if quote in part:
                    fname = part.split(quote)[1]
                    if fname.endswith(".json"):
                        json_refs.add((fname, i + 1))
    return json_refs

def check_json_files(py_files, project_root):
    missing_json = defaultdict(list)
    for pyf in py_files:
        refs = find_json_references(pyf)
        for ref, line in refs:
            # Try to resolve relative to script and project root
            local = os.path.join(os.path.dirname(pyf), ref)
            global_ = os.path.join(project_root, ref)
            if not (os.path.exists(local) or os.path.exists(global_)):
                missing_json[ref].append(f"{pyf}:{line}")
    return missing_json

def main(project_root):
    print(f"Scanning project: {project_root}\n{'='*60}")
    py_files = find_python_files(project_root)
    print(f"Found {len(py_files)} Python files.\n")

    print("Checking for broken/missing imports...")
    missing_imports = check_imports(py_files, project_root)
    if missing_imports:
        print("\nBroken or missing imports found:")
        for imp, files in missing_imports.items():
            print(f"  IMPORT: {imp}")
            for f in files:
                print(f"    in {f}")
    else:
        print("  No broken imports found.")

    print("\nChecking for missing JSON config/data files...")
    missing_json = check_json_files(py_files, project_root)
    if missing_json:
        print("\nMissing JSON files referenced:")
        for js, files in missing_json.items():
            print(f"  JSON FILE: {js}")
            for f in files:
                print(f"    in {f}")
    else:
        print("  No missing JSON references found.")

    print("\nScan complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_and_config_checker.py /path/to/your/project")
        sys.exit(1)
    main(os.path.abspath(sys.argv[1]))