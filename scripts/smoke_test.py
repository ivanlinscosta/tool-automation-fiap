#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from urllib import error, request


BASE_URL = os.getenv("QUANTUM_BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Lab-Group": os.getenv("QUANTUM_LAB_GROUP", "smoke-tests"),
    "X-Request-ID": "smoke-test-001",
}
TIMEOUT = 10


def fetch_json(path: str, *, method: str = "GET", payload: dict | None = None) -> tuple[int, object]:
    data = None
    headers = dict(HEADERS)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed


def run_check(name: str, func) -> bool:
    try:
        func()
        print(f"PASS {name}")
        return True
    except AssertionError as exc:
        print(f"FAIL {name}: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {name}: {exc}")
        return False


def main() -> int:
    checks = [
        (
            "GET /health",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "status", "ok"),
                )
            )(*fetch_json("/health")),
        ),
        (
            "GET /api/v1/health",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "status", "ok"),
                )
            )(*fetch_json("/api/v1/health")),
        ),
        (
            "GET /api/v1/customers/CUS-1001",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "id", "CUS-1001"),
                )
            )(*fetch_json("/api/v1/customers/CUS-1001")),
        ),
        (
            "GET /api/v1/orders/ORD-2026-10001",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "id", "ORD-2026-10001"),
                )
            )(*fetch_json("/api/v1/orders/ORD-2026-10001")),
        ),
        (
            "GET /api/v1/inventory/QTM-NBK-00123",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "sku", "QTM-NBK-00123"),
                    assert_field(payload, "total_available", 37),
                )
            )(*fetch_json("/api/v1/inventory/QTM-NBK-00123")),
        ),
        (
            "GET /api/v1/inventory/QTM-NBK-00150/availability (out of stock)",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "sku", "QTM-NBK-00150"),
                    assert_field(payload, "available", False),
                    assert_field(payload, "quantity", 0),
                )
            )(*fetch_json("/api/v1/inventory/QTM-NBK-00150/availability?postal_code=01310-100")),
        ),
        (
            "POST /api/v1/returns/check-eligibility (inside window)",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "eligible", True),
                    assert_field(payload, "reason", "within_return_window"),
                )
            )(
                *fetch_json(
                    "/api/v1/returns/check-eligibility",
                    method="POST",
                    payload={"order_id": "ORD-2026-10005", "sku": "QTM-AUD-01023"},
                )
            ),
        ),
        (
            "POST /api/v1/returns/check-eligibility (outside window)",
            lambda: (
                lambda status_code, payload: (
                    assert_status(status_code, 200),
                    assert_field(payload, "eligible", False),
                    assert_field(payload, "reason", "outside_return_window"),
                )
            )(
                *fetch_json(
                    "/api/v1/returns/check-eligibility",
                    method="POST",
                    payload={"order_id": "ORD-2026-10007", "sku": "QTM-BED-01089"},
                )
            ),
        ),
    ]

    passed = sum(1 for name, check in checks if run_check(name, check))
    total = len(checks)
    print(f"Summary: {passed}/{total} checks passed")
    return 0 if passed == total else 1


def assert_status(actual: int, expected: int) -> None:
    if actual != expected:
        raise AssertionError(f"expected HTTP {expected}, got {actual}")


def assert_field(payload: object, field: str, expected: object) -> None:
    if not isinstance(payload, dict):
        raise AssertionError(f"expected JSON object, got {type(payload).__name__}")
    actual = payload.get(field)
    if actual != expected:
        raise AssertionError(f"expected {field}={expected!r}, got {actual!r}")


if __name__ == "__main__":
    raise SystemExit(main())
