#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Repository Cleanup Utility for PyBit Bot

This script scans the repository to identify:
1. Duplicate/redundant files (same content with different names)
2. Potentially obsolete Python files (not imported by any other files)
3. Old config files that might have been migrated
4. Empty directories that can be removed
5. Files with similar names that might be confusing

Usage:
    python cleanup_repo.py [--delete] [--ignore-dir=dir1,dir2]

Options:
    --delete        Actually delete files identified as safe to remove (USE WITH CAUTION)
    --ignore-dir    Comma-separated list of directories to ignore
"""

import os
import sys
import hashlib
import re
import ast
import json
import argparse
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

# Global variables
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
KNOWN_CONFIG_PATHS = [
    "config.json",
    "config/indicator.json",
]
NEW_CONFIG_DIR = "pybit_bot/configs"


class CodeAnalyzer:
    """Analyzes Python code to find imports and references."""
    
    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.all_modules: Dict[str, str] = {}  # module_name -> file_path
        self.imports: Dict[str, Set[str]] = defaultdict(set)  # file_path -> imported_modules
        self.imported_by: Dict[str, Set[str]] = defaultdict(set)  # module_name -> importing_files
        
    def scan_python_files(self):
        """Scan all Python files in the repository."""
        for root, _, files in os.walk(self.repo_root):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, self.repo_root)
                    
                    # Skip virtual environments
                    if "venv" in rel_path.split(os.sep) or "env" in rel_path.split(os.sep):
                        continue
                    
                    # Convert file path to potential module name
                    module_path = rel_path.replace(os.sep, ".").replace(".py", "")
                    if module_path.startswith("."):
                        module_path = module_path[1:]
                        
                    self.all_modules[module_path] = filepath
                    
                    # Analyze imports in this file
                    self._analyze_file_imports(filepath)
    
    def _analyze_file_imports(self, filepath: str):
        """Analyze imports in a Python file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Handle regular imports (import x, import x.y)
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.imports[filepath].add(name.name)
                        self.imported_by[name.name].add(filepath)
                
                # Handle from imports (from x import y, from x.y import z)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    module_name = node.module
                    if node.level > 0:  # Relative imports
                        # Convert relative imports to absolute for our analysis
                        # This is a simplification; real resolution is more complex
                        rel_path = os.path.relpath(filepath, self.repo_root)
                        package_parts = rel_path.split(os.sep)[:-1]
                        if len(package_parts) >= node.level:
                            package = '.'.join(package_parts[:-node.level+1])
                            if package:
                                module_name = f"{package}.{module_name}"
                    
                    self.imports[filepath].add(module_name)
                    self.imported_by[module_name].add(filepath)
                    
                    # Also track imported names
                    for name in node.names:
                        full_name = f"{module_name}.{name.name}"
                        self.imported_by[full_name].add(filepath)
                        
        except Exception as e:
            print(f"Error analyzing imports in {filepath}: {str(e)}")
    
    def find_unused_modules(self) -> List[str]:
        """Find Python modules that are not imported by any other file."""
        used_modules = set()
        
        # Gather all modules that are imported by at least one file
        for imports in self.imports.values():
            for module in imports:
                # Check if this import matches any of our modules
                for known_module in self.all_modules:
                    if module == known_module or module.startswith(f"{known_module}."):
                        used_modules.add(known_module)
        
        # Find modules that are never imported
        unused_modules = []
        for module_name, filepath in self.all_modules.items():
            # Skip __init__.py, main files, and tests
            filename = os.path.basename(filepath)
            if (filename == "__init__.py" or 
                filename == "__main__.py" or 
                'test' in filename or
                'tests' in filepath):
                continue
                
            if module_name not in used_modules:
                # Check if it's imported with a different name
                module_parts = module_name.split(".")
                is_imported = False
                
                # Check if parent packages are imported
                for i in range(len(module_parts)):
                    partial_module = ".".join(module_parts[:i+1])
                    if partial_module in self.imported_by:
                        is_imported = True
                        break
                
                if not is_imported:
                    unused_modules.append(filepath)
        
        return unused_modules


class FileAnalyzer:
    """Analyzes files to find duplicates and obsolete configurations."""
    
    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.file_hashes: Dict[str, List[str]] = defaultdict(list)
        
    def compute_file_hashes(self, ignore_dirs: List[str] = None):
        """Compute hashes of all files for duplicate detection."""
        if ignore_dirs is None:
            ignore_dirs = []
            
        # Add common directories to ignore
        ignore_dirs.extend(['venv', 'env', '.git', '__pycache__', '.pytest_cache'])
        
        for root, dirs, files in os.walk(self.repo_root):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    file_hash = self._hash_file(filepath)
                    if file_hash:
                        self.file_hashes[file_hash].append(filepath)
                except Exception as e:
                    print(f"Error hashing {filepath}: {str(e)}")
    
    def _hash_file(self, filepath: str) -> Optional[str]:
        """Compute the SHA-256 hash of a file."""
        if os.path.getsize(filepath) > 50 * 1024 * 1024:  # Skip files > 50MB
            return None
            
        try:
            with open(filepath, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            return file_hash
        except Exception:
            return None
    
    def find_duplicate_files(self) -> List[List[str]]:
        """Find files with identical content."""
        duplicates = []
        for file_hash, filepaths in self.file_hashes.items():
            if len(filepaths) > 1:
                # Convert to relative paths for better readability
                rel_paths = [os.path.relpath(path, self.repo_root) for path in filepaths]
                duplicates.append(rel_paths)
        return duplicates
    
    def find_similar_named_files(self) -> List[List[str]]:
        """Find files with very similar names that might be confusing."""
        files_by_name: Dict[str, List[str]] = defaultdict(list)
        
        for root, _, files in os.walk(self.repo_root):
            for file in files:
                # Skip common non-source files
                if file.startswith('.') or file in ['README.md', 'LICENSE']:
                    continue
                    
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.repo_root)
                
                # Get base name without extension
                name_parts = file.split('.')
                if len(name_parts) > 1:
                    base_name = '.'.join(name_parts[:-1])
                else:
                    base_name = file
                
                files_by_name[base_name.lower()].append(rel_path)
        
        # Find similar names using Levenshtein distance
        similar_groups = []
        processed = set()
        
        all_names = list(files_by_name.keys())
        for i, name1 in enumerate(all_names):
            if name1 in processed:
                continue
                
            similar_files = []
            
            for name2 in all_names[i+1:]:
                if name2 in processed:
                    continue
                    
                # Simple similarity check
                if name1 != name2 and (name1 in name2 or name2 in name1 or 
                                       self._levenshtein_distance(name1, name2) <= 2):
                    similar_files.extend(files_by_name[name2])
                    processed.add(name2)
            
            if similar_files:
                similar_group = files_by_name[name1] + similar_files
                similar_groups.append(similar_group)
                processed.add(name1)
        
        return similar_groups
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Compute the Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
            
        if len(s2) == 0:
            return len(s1)
            
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Calculate insertions, deletions and substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                
                # Get minimum
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
            
        return previous_row[-1]
    
    def find_old_config_files(self) -> List[str]:
        """Find old configuration files that might have been migrated."""
        old_configs = []
        
        # Check if new config directory exists
        if os.path.exists(os.path.join(self.repo_root, NEW_CONFIG_DIR)):
            # Check for old config files
            for config_path in KNOWN_CONFIG_PATHS:
                full_path = os.path.join(self.repo_root, config_path)
                if os.path.exists(full_path):
                    old_configs.append(os.path.relpath(full_path, self.repo_root))
        
        return old_configs
    
    def find_empty_directories(self) -> List[str]:
        """Find empty directories that can be removed."""
        empty_dirs = []
        
        for root, dirs, files in os.walk(self.repo_root, topdown=False):
            # Skip .git and virtual environments
            if ".git" in root.split(os.sep) or "venv" in root.split(os.sep) or "env" in root.split(os.sep):
                continue
                
            # Check if directory is empty or only contains __pycache__
            if not files:
                has_real_dirs = False
                for dir_name in dirs:
                    if dir_name != "__pycache__":
                        has_real_dirs = True
                        break
                        
                if not has_real_dirs:
                    empty_dirs.append(os.path.relpath(root, self.repo_root))
        
        return empty_dirs


def format_report(
    duplicates: List[List[str]],
    unused_modules: List[str],
    old_configs: List[str],
    empty_dirs: List[str],
    similar_files: List[List[str]]
) -> str:
    """Format the cleanup report."""
    report = []
    
    report.append("=" * 80)
    report.append("PYBIT BOT REPOSITORY CLEANUP REPORT")
    report.append("=" * 80)
    
    # Duplicate files
    report.append("\n1. DUPLICATE FILES")
    report.append("-" * 80)
    if duplicates:
        for i, group in enumerate(duplicates, 1):
            report.append(f"Group {i}:")
            for path in group:
                report.append(f"  - {path}")
            report.append("")
    else:
        report.append("No duplicate files found.")
    
    # Unused Python modules
    report.append("\n2. POTENTIALLY UNUSED PYTHON MODULES")
    report.append("-" * 80)
    report.append("These files are not imported by any other files in the repository:")
    if unused_modules:
        for path in unused_modules:
            rel_path = os.path.relpath(path, REPO_ROOT)
            report.append(f"  - {rel_path}")
    else:
        report.append("No unused Python modules found.")
    
    # Old configuration files
    report.append("\n3. OLD CONFIGURATION FILES")
    report.append("-" * 80)
    report.append("These configuration files might have been migrated to the new structure:")
    if old_configs:
        for path in old_configs:
            report.append(f"  - {path}")
    else:
        report.append("No old configuration files found.")
    
    # Empty directories
    report.append("\n4. EMPTY DIRECTORIES")
    report.append("-" * 80)
    if empty_dirs:
        for path in empty_dirs:
            report.append(f"  - {path}")
    else:
        report.append("No empty directories found.")
    
    # Similar file names
    report.append("\n5. FILES WITH SIMILAR NAMES")
    report.append("-" * 80)
    report.append("These files have similar names and might be confusing or redundant:")
    if similar_files:
        for i, group in enumerate(similar_files, 1):
            report.append(f"Group {i}:")
            for path in group:
                report.append(f"  - {path}")
            report.append("")
    else:
        report.append("No files with similar names found.")
    
    report.append("\n" + "=" * 80)
    report.append("RECOMMENDATIONS")
    report.append("=" * 80)
    
    # Add recommendations
    recommendations = []
    
    if duplicates:
        recommendations.append("- Review duplicate files and keep only one copy")
    
    if unused_modules:
        recommendations.append("- Consider removing unused Python modules if they're not needed")
    
    if old_configs:
        recommendations.append("- Remove old configuration files if all settings have been migrated")
    
    if empty_dirs:
        recommendations.append("- Clean up empty directories")
    
    if similar_files:
        recommendations.append("- Review files with similar names to reduce confusion")
    
    if recommendations:
        for rec in recommendations:
            report.append(rec)
    else:
        report.append("No cleanup actions needed. Repository is well-organized!")
    
    report.append("\nTo automatically clean up some issues, run:")
    report.append("python cleanup_repo.py --delete")
    report.append("\n")
    report.append("NOTE: Always commit your changes before cleanup in case you need to restore files.")
    
    return "\n".join(report)


def clean_up_repository(
    duplicates: List[List[str]],
    unused_modules: List[str],
    old_configs: List[str],
    empty_dirs: List[str]
):
    """Clean up the repository based on analysis results."""
    print("\nStarting repository cleanup...")
    
    # Only delete the second+ copy of duplicate files
    for group in duplicates:
        # Keep the first file, delete others
        print(f"Keeping {group[0]}, removing {len(group)-1} duplicates")
        for path in group[1:]:
            full_path = os.path.join(REPO_ROOT, path)
            os.remove(full_path)
            print(f"  Deleted: {path}")
    
    # Remove old config files
    for path in old_configs:
        full_path = os.path.join(REPO_ROOT, path)
        os.remove(full_path)
        print(f"Deleted old config: {path}")
    
    # Remove empty directories
    for path in empty_dirs:
        full_path = os.path.join(REPO_ROOT, path)
        try:
            os.rmdir(full_path)
            print(f"Removed empty directory: {path}")
        except OSError:
            print(f"Could not remove directory: {path} (it might not be empty anymore)")
    
    # We do NOT automatically delete unused modules as they might be needed for direct execution
    # Just print a warning
    if unused_modules:
        print("\nWARNING: The following potentially unused modules were NOT deleted automatically:")
        for path in unused_modules:
            rel_path = os.path.relpath(path, REPO_ROOT)
            print(f"  - {rel_path}")
        print("Review these files manually and delete if not needed.")
    
    print("\nCleanup completed!")


def main():
    """Main function to run the repository cleanup utility."""
    parser = argparse.ArgumentParser(description="Repository Cleanup Utility")
    parser.add_argument("--delete", action="store_true", help="Delete files identified as safe to remove")
    parser.add_argument("--ignore-dir", type=str, help="Comma-separated list of directories to ignore")
    
    args = parser.parse_args()
    
    # Get directories to ignore
    ignore_dirs = []
    if args.ignore_dir:
        ignore_dirs = [d.strip() for d in args.ignore_dir.split(",")]
    
    print(f"Analyzing repository at {REPO_ROOT}...")
    
    # Analyze code
    code_analyzer = CodeAnalyzer(REPO_ROOT)
    code_analyzer.scan_python_files()
    unused_modules = code_analyzer.find_unused_modules()
    
    # Analyze files
    file_analyzer = FileAnalyzer(REPO_ROOT)
    file_analyzer.compute_file_hashes(ignore_dirs)
    
    duplicates = file_analyzer.find_duplicate_files()
    old_configs = file_analyzer.find_old_config_files()
    empty_dirs = file_analyzer.find_empty_directories()
    similar_files = file_analyzer.find_similar_named_files()
    
    # Generate report
    report = format_report(
        duplicates,
        unused_modules,
        old_configs,
        empty_dirs,
        similar_files
    )
    
    print(report)
    
    # Save report to file
    with open("cleanup_report.txt", "w") as f:
        f.write(report)
    
    print(f"\nReport saved to {os.path.join(REPO_ROOT, 'cleanup_report.txt')}")
    
    # Clean up if requested
    if args.delete:
        response = input("\nWARNING: This will delete files. Are you sure? (y/n): ")
        if response.lower() == 'y':
            clean_up_repository(
                duplicates,
                unused_modules,
                old_configs,
                empty_dirs
            )
        else:
            print("Cleanup cancelled.")


if __name__ == "__main__":
    main()