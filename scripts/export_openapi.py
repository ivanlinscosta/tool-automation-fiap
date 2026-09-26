#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from app.main import app


OPENAPI_PATH = Path(__file__).resolve().parents[1] / "docs" / "openapi.yaml"


def main() -> None:
    spec = app.openapi()
    OPENAPI_PATH.write_text(
        yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"OpenAPI spec written to {OPENAPI_PATH} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
