from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from app.labs.registry import GROUP_TAGS
from app.main import app


COLLECTION_PATH = (
    Path(__file__).resolve().parents[1]
    / "postman"
    / "Quantum-Commerce-API.postman_collection.json"
)
ENVIRONMENT_PATH = COLLECTION_PATH.with_name("Quantum-Commerce-API.postman_environment.json")
LABS_FOLDER_NAME = "Workflow Labs"
LABS_PREFIX = "/api/v1/labs"
HTTP_METHODS = ("get", "post", "put", "patch", "delete")

PATH_PARAM_FALLBACKS = {
    "group_id": "01",
    "wa_id": "5511999999999",
    "cpf": "11144477735",
    "cnpj": "11222333000181",
    "telefone": "5511999999999",
    "email": "aluno@exemplo.com",
    "scenario": "success",
}


def path_segment_value(name: str, schema: dict[str, Any]) -> str:
    enum = schema.get("enum")
    if enum:
        return str(enum[0])
    example = schema.get("example")
    if example is not None:
        return str(example)
    fallback = PATH_PARAM_FALLBACKS.get(name)
    if fallback is not None:
        return fallback
    if name.endswith("_id") or name in {"id", "codigo"}:
        return "1"
    return "1"


def build_url(
    raw_path: str,
    parameters: list[dict[str, Any]],
    query: list[dict[str, Any]],
) -> dict[str, Any]:
    segments = raw_path.strip("/").split("/")
    path_parts: list[str] = []
    lookup: dict[str, dict[str, Any]] = {}

    for segment in segments:
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            parameter = next(
                (item for item in parameters if item.get("name") == name and item.get("in") == "path"),
                {},
            )
            path_parts.append(f":{name}")
            lookup[name] = path_parameter(name, parameter)
        else:
            path_parts.append(segment)

    url: dict[str, Any] = {
        "raw": "{{baseUrl}}" + raw_path,
        "host": ["{{baseUrl}}"],
        "path": path_parts,
    }
    if query:
        url["query"] = query
    return url


def path_parameter(name: str, parameter: dict[str, Any]) -> dict[str, Any]:
    schema = parameter.get("schema") or {}
    return {
        "key": name,
        "value": path_segment_value(name, schema),
        "description": parameter.get("description", ""),
    }


def query_parameter(parameter: dict[str, Any]) -> dict[str, Any]:
    schema = parameter.get("schema") or {}
    default = parameter.get("schema", {}).get("default")
    if default is None:
        default = schema.get("default")
    enum = schema.get("enum")
    if enum:
        value = str(enum[0])
    elif default is not None:
        value = str(default)
    else:
        example = parameter.get("example", schema.get("example"))
        value = str(example) if example is not None else ""
    return {
        "key": parameter["name"],
        "value": value,
        "description": parameter.get("description", ""),
    }


def request_body_example(operation: dict[str, Any]) -> list[dict[str, Any]]:
    body = operation.get("requestBody")
    if not body:
        return []
    content = (body.get("content") or {}).get("application/json")
    if not content:
        return []
    example = content.get("example")
    if example is None:
        schema_example = ((content.get("schema") or {}).get("example"))
        example = schema_example
    if example is None:
        return []
    return [
        {
            "key": "raw",
            "value": json.dumps(example, indent=2, ensure_ascii=False),
            "type": "json",
        }
    ]


def request_name(operation_id: str, summary: str | None) -> str:
    if summary:
        return summary
    return operation_id.replace("labs_group", "Group ").replace("_", " ").title()


def build_request(
    raw_path: str,
    method: str,
    operation: dict[str, Any],
) -> dict[str, Any]:
    parameters = operation.get("parameters") or []
    path_params = [item for item in parameters if item.get("in") == "path"]
    query = [
        query_parameter(item)
        for item in parameters
        if item.get("in") == "query"
    ]
    scenario_present = any(item["key"] == "scenario" for item in query)

    headers = [
        {"key": "X-Lab-Group", "value": "grupo-01", "type": "text"},
        {"key": "X-Request-ID", "value": "req-{{$guid}}", "type": "text"},
    ]
    if "/instructor/" in raw_path or raw_path.endswith("/integrity") or raw_path.endswith("/reset"):
        headers.append(
            {"key": "X-Instructor-Key", "value": "{{instructorKey}}", "type": "text"}
        )

    request: dict[str, Any] = {
        "method": method.upper(),
        "header": headers,
        "url": build_url(raw_path, path_params, query),
        "description": operation.get("description", ""),
    }
    body = request_body_example(operation)
    if body:
        request["body"] = {"mode": "raw", "raw": body[0]["value"], "options": {"raw": {"language": "json"}}}

    if not scenario_present:
        request["url"].setdefault("query", []).append(
            {
                "key": "scenario",
                "value": "success",
                "description": "success | validation_error | not_found | duplicate | timeout | server_error",
            }
        )

    response_codes = sorted(
        {
            str(code)
            for code in (operation.get("responses") or {})
            if str(code).startswith(("2", "4", "5"))
        }
    )
    return {
        "name": request_name(operation.get("operationId", raw_path), operation.get("summary")),
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        "pm.test('respondeu', function () {",
                        f"  pm.expect([{', '.join(response_codes) or '200'}]).to.include(pm.response.code);",
                        "});",
                    ],
                },
            }
        ],
        "request": request,
    }


def group_of(raw_path: str, operation: dict[str, Any]) -> str:
    if not raw_path.startswith(LABS_PREFIX):
        return "Other"
    for tag in operation.get("tags") or []:
        group_number = GROUP_TAGS.get(tag)
        if group_number is not None:
            return f"Group {group_number}"
        if tag.startswith("Lab -"):
            return "Platform"
    remainder = raw_path[len(LABS_PREFIX) :].strip("/")
    if not remainder or "{group_id}" not in remainder:
        return "Platform" if remainder else "Other"
    return "Other"


def folder_of(raw_path: str) -> str:
    if "/instructor/" in raw_path or raw_path.endswith("/integrity") or raw_path.endswith("/reset"):
        return "Instructor"
    return "Endpoints"


def collect() -> dict[str, dict[str, list[dict[str, Any]]]]:
    spec = app.openapi()
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for raw_path, operations in sorted(spec["paths"].items()):
        if not raw_path.startswith(LABS_PREFIX):
            continue
        for method, operation in operations.items():
            if method not in HTTP_METHODS:
                continue
            group = group_of(raw_path, operation)
            folder = folder_of(raw_path)
            buckets.setdefault(group, {}).setdefault(folder, []).append(
                build_request(raw_path, method, operation)
            )
    return buckets


def build_labs_folder() -> dict[str, Any]:
    buckets = collect()
    group_order = ["Platform"] + [f"Group {index:02d}" for index in range(1, 13)] + ["Other"]
    items: list[dict[str, Any]] = []
    for group in group_order:
        if group not in buckets:
            continue
        sub_items: list[dict[str, Any]] = []
        for folder in ("Endpoints", "Instructor"):
            if folder not in buckets[group]:
                continue
            requests = sorted(buckets[group][folder], key=lambda item: item["name"])
            if folder == "Endpoints":
                sub_items.extend(requests)
            else:
                sub_items.append(
                    {
                        "name": folder,
                        "item": requests,
                        "description": "Endpoints restritos a instrutores (header X-Instructor-Key).",
                    }
                )
        items.append({"name": group, "item": sub_items})
    return {
        "name": LABS_FOLDER_NAME,
        "description": (
            "Os 12 laboratorios deterministicos. Todos os endpoints aceitam o query param "
            "`scenario` para simular falhas: success, validation_error (422), not_found (404), "
            "duplicate (409), timeout (504) e server_error (500)."
        ),
        "item": items,
    }


def count_requests(items: list[dict[str, Any]]) -> int:
    return sum(
        count_requests(item["item"]) if "item" in item else 1
        for item in items
    )


def main() -> None:
    collection = json.loads(COLLECTION_PATH.read_text(encoding="utf-8"))
    collection["item"] = [
        item for item in collection.get("item", []) if item.get("name") != LABS_FOLDER_NAME
    ]
    labs_folder = build_labs_folder()
    collection["item"].append(labs_folder)

    variables = {variable["key"]: variable for variable in collection.get("variable", [])}
    variables.setdefault(
        "instructorKey",
        {"key": "instructorKey", "value": "chave-de-instrutor", "type": "string"},
    )
    collection["variable"] = list(variables.values())

    COLLECTION_PATH.write_text(
        json.dumps(collection, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    environment = json.loads(ENVIRONMENT_PATH.read_text(encoding="utf-8"))
    env_values = {value["key"]: value for value in environment.get("values", [])}
    env_values.setdefault(
        "instructorKey",
        {
            "key": "instructorKey",
            "value": "chave-de-instrutor",
            "type": "default",
            "enabled": True,
        },
    )
    environment["values"] = list(env_values.values())
    ENVIRONMENT_PATH.write_text(
        json.dumps(environment, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    total = count_requests(labs_folder["item"])
    print(f"Postman collection updated: {LABS_FOLDER_NAME} with {total} requests")


if __name__ == "__main__":
    main()
