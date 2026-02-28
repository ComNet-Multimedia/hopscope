#!/usr/bin/env python3
"""Runs mtr periodically and saves results to SQLite."""
import subprocess
import json
import time
import os
import signal
import sys

from db import init_db, save_run

INTERVAL_SEC = int(os.environ.get("MTR_INTERVAL", "30"))
TARGET = os.environ.get("MTR_TARGET", "8.8.8.8")


def run_mtr(target: str) -> dict | None:
    try:
        result = subprocess.run(
            ["mtr", "-c", "1", "-j", target],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            if "Failure to open" in err and "socket" in err:
                print(
                    "mtr wymaga uprawnień root (raw sockets). Na macOS uruchom:\n"
                    "  sudo python backend/collector.py",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(f"mtr exited {result.returncode}: {err}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except FileNotFoundError:
        print("mtr not found. Install with: brew install mtr (macOS) or apt install mtr (Linux)", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid mtr JSON: {e}", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("mtr timed out", file=sys.stderr)
        return None


def main():
    init_db()
    print(f"Collector started: target={TARGET}, interval={INTERVAL_SEC}s (Ctrl+C to stop)")
    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    while running:
        data = run_mtr(TARGET)
        if data:
            report = data.get("report", {})
            mtr_info = report.get("mtr", {})
            hubs = report.get("hubs", [])
            if hubs:
                run_id = save_run(
                    target=mtr_info.get("dst", TARGET),
                    src=mtr_info.get("src"),
                    hubs=hubs,
                )
                print(f"Saved run {run_id} ({len(hubs)} hops)")
            else:
                print("No hubs in response, skipping")
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
