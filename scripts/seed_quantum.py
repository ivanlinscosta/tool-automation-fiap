#!/usr/bin/env python3

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from app.db.seed import seed_data


def main() -> int:
    seed_data()
    print("Quantum Commerce seed completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
