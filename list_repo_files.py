#!/usr/bin/env python3
import os
import sys

def list_files(start_path='.'):
    """
    Recursively prints all directories and files under start_path
    in a tree-like format.
    """
    for root, dirs, files in os.walk(start_path):
        # compute indent level based on depth
        depth = root.replace(start_path, '').count(os.sep)
        indent = ' ' * 4 * depth
        # print directory
        print(f"{indent}{os.path.basename(root)}/")
        # print files in directory
        for filename in files:
            print(f"{indent}    {filename}")

if __name__ == "__main__":
    # allow passing a custom path, default to repo root ('.')
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    list_files(path)
