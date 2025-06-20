#!/usr/bin/env python3
"""
generate_mapping.py

Scan:
  pybit_bot/core/*.py
  pybit_bot/managers/*.py
  pybit_bot/engine.py

for calls like:

    self.client.foo(...)
    self.order_client.bar(...)
    self.data_manager.baz(...)
    self.order_manager.quux(...)
    self.strategy_manager.<...>
    self.tpsl_manager.<...>

and output a CSV:

    File,Class.Method,Attr,Method,Endpoint
"""
import ast
import sys
import csv
from pathlib import Path

# attributes on self() we want to track
LAYER_ATTRS = (
    "client",
    "order_client",
    "data_manager",
    "order_manager",
    "strategy_manager",
    "tpsl_manager",
)

# relative globs from the repo‐root you’ll pass in
SEARCH_PATHS = [
    ("core", "*.py"),
    ("managers", "*.py"),
    ("",     "engine.py"),
]

def extract_calls(path: Path, root: Path):
    """Parse path, find calls of self.<layer>.<method>(...) and optionally capture endpoint."""
    rel = str(path.relative_to(root))
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    out = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cls = node.name
            for fn in node.body:
                if not isinstance(fn, ast.FunctionDef):
                    continue
                mth = fn.name
                for call in ast.walk(fn):
                    if not isinstance(call, ast.Call):
                        continue
                    f = call.func
                    # look for self.<layer>.<method>
                    if isinstance(f, ast.Attribute) \
                    and isinstance(f.value, ast.Attribute) \
                    and isinstance(f.value.value, ast.Name) \
                    and f.value.value.id == "self" \
                    and f.value.attr in LAYER_ATTRS:
                        layer = f.value.attr
                        method = f.attr
                        endpoint = ""
                        # if raw HTTP, grab the literal path arg
                        if layer == "client" and method == "_make_request":
                            if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                                endpoint = call.args[1].value
                        out.append([rel, f"{cls}.{mth}", layer, method, endpoint])
    return out

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_mapping.py <path_to_pybit_bot/pybit_bot>")
        sys.exit(1)

    root = Path(sys.argv[1])
    writer = csv.writer(sys.stdout)
    writer.writerow(["File","Class.Method","Attr","Method","Endpoint"])

    for subdir, pattern in SEARCH_PATHS:
        base = root / subdir
        if not base.exists():
            continue
        # glob works for both "*.py" and "engine.py"
        for file in sorted(base.glob(pattern)):
            if file.is_file():
                for rec in extract_calls(file, root):
                    writer.writerow(rec)
