#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "flowdesk.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete the FlowDesk Lab SQLite database so seed data is recreated on next startup.")
    _ = parser.add_argument("--force", action="store_true", help="Skip the confirmation prompt.")
    return parser.parse_args()


def confirm_delete() -> bool:
    print(f"This will permanently delete: {DB_PATH}")
    print("On the next API startup, the database tables and seed data will be recreated.")
    answer = input("Type 'yes' to continue: ").strip().lower()
    return answer == "yes"


def main() -> int:
    args = parse_args()
    force_value: object = getattr(args, "force", False)
    force = force_value is True

    if not DB_PATH.exists():
        print(f"Database file not found: {DB_PATH}")
        return 0

    if not force and not confirm_delete():
        print("Aborted. Database was not deleted.")
        return 1

    try:
        DB_PATH.unlink()
    except OSError as exc:
        print(f"Failed to delete database: {exc}", file=sys.stderr)
        return 1

    print(f"Deleted database file: {DB_PATH}")
    print("Restart the API to recreate the SQLite database and seed records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
