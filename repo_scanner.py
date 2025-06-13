"""
repo_scanner.py

Scans the current repo for:
- File/folder structure mapping (skips venv, .venv, env, .git)
- Python import statements
- Dangling or missing imports (modules referenced but not found in the repo)
- Potential connection issues (files not referenced/imported anywhere)

Usage:
    python repo_scanner.py [path_to_repo_root]

If no path is given, uses the current directory.
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Ignore these folders (case-insensitive)
IGNORE_FOLDERS = {"venv", ".venv", "env", ".git", "__pycache__"}

PYTHON_FILE_REGEX = re.compile(r".*\.py$")
IMPORT_REGEX = re.compile(r"^(?:from\s+([.\w_]+)\s+import|import\s+([.\w_]+))", re.MULTILINE)

def map_file_structure(repo_path):
    print("Project File Structure:")
    for root, dirs, files in os.walk(repo_path):
        # Remove ignored folders in-place
        dirs[:] = [d for d in dirs if d.lower() not in IGNORE_FOLDERS]
        indent = '    ' * (len(Path(root).relative_to(repo_path).parts))
        print(f"{indent}{os.path.basename(root)}/")
        for f in files:
            print(f"{indent}    {f}")
    print("\n")

def list_python_files(repo_path):
    py_files = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORE_FOLDERS]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files

def get_imports_from_file(file_path):
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    imports = []
    for match in IMPORT_REGEX.finditer(content):
        module = match.group(1) or match.group(2)
        if module:
            imports.append(module.split('.')[0])
    return imports

def build_import_map(py_files, repo_path):
    import_map = defaultdict(list)
    reverse_map = defaultdict(list)
    all_modules = set()
    for file in py_files:
        rel_file = os.path.relpath(file, repo_path)
        imports = get_imports_from_file(file)
        import_map[rel_file] = imports
        for imp in imports:
            reverse_map[imp].append(rel_file)
        module_name = Path(rel_file).with_suffix('').as_posix().replace('/', '.')
        all_modules.add(module_name.split('.')[-1])
    return import_map, reverse_map, all_modules

def check_missing_imports(import_map, all_modules):
    missing = defaultdict(list)
    std_libs = set(sys.builtin_module_names)
    for file, imports in import_map.items():
        for imp in imports:
            # Only flag as missing if not in project modules and not a stdlib
            if imp not in all_modules and imp not in std_libs:
                missing[file].append(imp)
    return missing

def find_unreferenced_files(import_map, all_modules):
    referenced = set()
    for imports in import_map.values():
        referenced.update(imports)
    unreferenced = all_modules - referenced
    return unreferenced

def main():
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        repo_path = os.getcwd()

    print(f"Scanning repo: {repo_path}")
    map_file_structure(repo_path)

    py_files = list_python_files(repo_path)
    print(f"Found {len(py_files)} Python files.\n")

    import_map, reverse_map, all_modules = build_import_map(py_files, repo_path)

    print("=== Import Dependencies ===")
    for file, imports in import_map.items():
        print(f"{file}: {imports}")
    print()

    missing = check_missing_imports(import_map, all_modules)
    print("=== Missing/Unresolved Imports (in project scope) ===")
    for file, missing_imports in missing.items():
        if missing_imports:
            print(f"{file}: {missing_imports}")
    if not any(missing.values()):
        print("None detected.")
    print()

    unreferenced = find_unreferenced_files(import_map, all_modules)
    print("=== Files/Modules Not Imported Anywhere ===")
    for module in sorted(unreferenced):
        print(module)
    if not unreferenced:
        print("None - all modules are referenced somewhere.")
    print()
    print("=== Scan Complete ===")

if __name__ == "__main__":
    main()