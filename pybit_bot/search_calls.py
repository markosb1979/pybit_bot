#!/usr/bin/env python3
import os
import re
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Scan for self.client / self.order_client calls across core, managers and engine.py"
    )
    parser.add_argument(
        "base_dir",
        help="Path to your pybit_bot/pybit_bot directory (e.g. G:\\My Drive\\MyBotFolder\\Bybit\\pybit_bot\\pybit_bot)"
    )
    args = parser.parse_args()

    pattern = re.compile(r"self\.(?:client|order_client)\.")
    base = args.base_dir

    # collect files under core/ and managers/, plus engine.py
    files = []
    for sub in ("core", "managers"):
        root = os.path.join(base, sub)
        for dirpath, _, fnames in os.walk(root):
            for f in fnames:
                if f.endswith(".py"):
                    files.append(os.path.join(dirpath, f))
    engine_py = os.path.join(base, "engine.py")
    if os.path.isfile(engine_py):
        files.append(engine_py)

    for path in sorted(files):
        rel = os.path.relpath(path, base)
        with open(path, "r", encoding="utf-8") as rf:
            for lineno, line in enumerate(rf, 1):
                if pattern.search(line):
                    print(f"{rel}:{lineno}:    {line.rstrip()}")

if __name__ == "__main__":
    main()
