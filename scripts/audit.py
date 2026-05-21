"""Read-only viewer for the audit log of server-modifying actions."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import json

import _client


def show(tail=None):
    if not _client.AUDIT_FILE.exists():
        print(f"No audit log yet at {_client.AUDIT_FILE}")
        return
    lines = _client.AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    if tail:
        lines = lines[-tail:]
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            print(line)
            continue
        ts = rec.get("ts", "?")
        action = rec.get("action", "?")
        extra = " ".join(f"{k}={v}" for k, v in rec.items()
                         if k not in ("ts", "action"))
        print(f"{ts}  {action}  {extra}")


def main():
    p = argparse.ArgumentParser(description="View the write-action audit log.")
    p.add_argument("--tail", type=int, help="Show only the last N entries.")
    args = p.parse_args()
    show(tail=args.tail)


if __name__ == "__main__":
    main()
