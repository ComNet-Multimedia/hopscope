#!/usr/bin/env python3
"""One-off import of MTR JSON from stdin or file. Example: mtr -c 1 -j google.com | python backend/import_mtr_json.py"""
import json
import sys
from pathlib import Path

# run from repo root
sys.path.insert(0, str(Path(__file__).parent))
from db import init_db, save_run

def main():
    init_db()
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        print("Paste MTR JSON (one object) and press Ctrl+D:")
        raw = sys.stdin.read()
    data = json.loads(raw)
    report = data.get("report", {})
    mtr_info = report.get("mtr", {})
    hubs = report.get("hubs", [])
    if not hubs:
        print("No hubs in JSON", file=sys.stderr)
        sys.exit(1)
    run_id = save_run(
        target=mtr_info.get("dst", "unknown"),
        src=mtr_info.get("src"),
        hubs=hubs,
    )
    print(f"Imported run {run_id} ({len(hubs)} hops)")

if __name__ == "__main__":
    main()
