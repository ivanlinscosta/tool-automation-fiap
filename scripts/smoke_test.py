#!/usr/bin/env python3
# pyright: reportMissingModuleSource=false

from __future__ import annotations

import json
import os
import sys
from typing import cast

try:
    import requests
except ModuleNotFoundError:
    requests = None


BASE_URL = os.getenv("FLOWDESK_BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "Content-Type": "application/json",
    "X-Student-ID": os.getenv("FLOWDESK_STUDENT_ID", "grupo-01"),
    "X-Request-ID": "smoke-test-001",
}
TIMEOUT = 10


def colorize(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text

    codes = {
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "cyan": "36",
        "bold": "1",
    }
    code = codes.get(color)
    return f"\033[{code}m{text}\033[0m" if code else text


def print_step(label: str, message: str, color: str = "blue") -> None:
    print(f"{colorize(label, 'bold')} {colorize(message, color)}")


def request_json(
    method: str,
    path: str,
    *,
    expected_status: int,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    if requests is None:
        raise RuntimeError("The 'requests' package is not installed for this Python interpreter. Install it with 'pip install requests'.")

    url = f"{BASE_URL}{path}"
    try:
        response = requests.request(method, url, headers=HEADERS, json=payload, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed for {method} {path}: {exc}") from exc

    if response.status_code != expected_status:
        safe_body = response.text[:300].strip()
        raise RuntimeError(
            f"Unexpected status for {method} {path}: {response.status_code} (expected {expected_status}). Body: {safe_body}"
        )

    try:
        data = cast(object, json.loads(response.text))
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON returned by {method} {path}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected JSON shape returned by {method} {path}: expected an object")

    return cast(dict[str, object], data)


def request_list(
    method: str,
    path: str,
    *,
    expected_status: int,
) -> list[object]:
    if requests is None:
        raise RuntimeError("The 'requests' package is not installed.")

    url = f"{BASE_URL}{path}"
    try:
        response = requests.request(method, url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed for {method} {path}: {exc}") from exc

    if response.status_code != expected_status:
        safe_body = response.text[:300].strip()
        raise RuntimeError(
            f"Unexpected status for {method} {path}: {response.status_code} (expected {expected_status}). Body: {safe_body}"
        )

    try:
        data = json.loads(response.text)
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON returned by {method} {path}") from exc

    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected JSON shape returned by {method} {path}: expected a list")

    return data


def main() -> int:
    print_step("Base URL:", BASE_URL, "cyan")

    try:
        health = request_json("GET", "/health", expected_status=200)
        print_step("Health:", f"{health.get('status')} / version {health.get('version')}", "green")

        student = request_json("GET", "/api/v1/students/STU001", expected_status=200)
        print_step("Student:", f"{student.get('name')} ({student.get('course')})", "green")

        dept = request_json("GET", "/api/v1/departments/digital_learning", expected_status=200)
        print_step("Department:", str(dept.get("department", "<unknown>")), "green")

        search = request_json("GET", "/api/v1/knowledge/search?q=acesso+ambiente", expected_status=200)
        results = search.get("results", [])
        print_step("Knowledge:", f"{len(results)} results found", "green")

        priority = request_json(
            "POST",
            "/api/v1/priority/check",
            expected_status=200,
            payload={
                "student_id": "STU001",
                "category": "digital_learning",
                "impact": "high",
                "urgency": "high",
            },
        )
        print_step("Priority:", str(priority.get("priority", "<unknown>")), "green")

        req = request_json(
            "POST",
            "/api/v1/requests",
            expected_status=201,
            payload={
                "student_id": "STU001",
                "category": "digital_learning",
                "summary": "Smoke test request",
                "description": "Request created automatically by smoke test.",
                "source": "smoke_test",
            },
        )
        request_id = str(req.get("request_id", "<unknown>"))
        protocol = str(req.get("protocol", "<unknown>"))
        print_step("Request created:", f"{request_id} ({protocol})", "green")

        fetched = request_json("GET", f"/api/v1/requests/{request_id}", expected_status=200)
        print_step("Request status:", str(fetched.get("status", "<unknown>")), "green")

        events = request_list("GET", "/api/v1/events", expected_status=200)
        print_step("Events:", f"{len(events)} audit events", "green")

        print(colorize("Smoke test completed successfully.", "green"))
        return 0
    except RuntimeError as exc:
        print(colorize(f"Smoke test failed: {exc}", "red"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
