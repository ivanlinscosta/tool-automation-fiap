import re

import pytest
from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-support-01"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


def _create_case(client: TestClient, **header_overrides: str):
    return client.post(
        "/api/v1/support/cases",
        headers=_headers(**header_overrides),
        json={
            "customer_id": "CUS-1001",
            "category": "delivery",
            "summary": "Package delayed",
            "description": "Customer reports the package has not arrived yet.",
        },
    )


@pytest.mark.parametrize(
    ("impact", "urgency", "priority", "sla_hours"),
    [
        ("high", "high", "P1", 2),
        ("high", "medium", "P2", 4),
        ("medium", "high", "P2", 4),
        ("medium", "medium", "P3", 8),
        ("high", "low", "P3", 8),
        ("low", "high", "P3", 8),
        ("low", "low", "P4", 24),
        ("low", "medium", "P4", 24),
        ("medium", "low", "P4", 24),
    ],
)
def test_priority_matrix_returns_expected_priority_and_sla(impact: str, urgency: str, priority: str, sla_hours: int):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/support/priority/check",
            headers=_headers(),
            json={"category": "delivery", "impact": impact, "urgency": urgency},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == priority
    assert data["sla_hours"] == sla_hours
    assert "Category 'delivery' was classified as" in data["rationale"]


def test_priority_check_requires_impact():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/support/priority/check",
            headers=_headers(),
            json={"category": "delivery", "urgency": "high"},
        )

    assert response.status_code == 422
    assert any(item["loc"][-1] == "impact" for item in response.json()["detail"])


def test_create_support_case_returns_expected_ids_and_default_priority_on_detail_fetch():
    with TestClient(app) as client:
        created = _create_case(client)
        created_data = created.json()
        detail = client.get(f"/api/v1/support/cases/{created_data['case_id']}", headers=_headers())

    assert created.status_code == 201
    assert created_data == {
        "case_id": "CASE-2026-10021",
        "status": "open",
        "protocol": "QCS-10021",
    }
    assert re.fullmatch(r"CASE-2026-\d{5}", created_data["case_id"])
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["case_id"] == "CASE-2026-10021"
    assert detail_data["protocol"] == "QCS-10021"
    assert detail_data["customer_id"] == "CUS-1001"
    assert detail_data["category"] == "delivery"
    assert detail_data["summary"] == "Package delayed"
    assert detail_data["description"] == "Customer reports the package has not arrived yet."
    assert detail_data["status"] == "open"
    assert detail_data["priority"] == "P3"
    assert detail_data["lab_group"] == LAB_GROUP
    assert detail_data["updated_at"] is None
    assert detail_data["created_at"] is not None


def test_create_support_case_replays_with_same_idempotency_key_and_conflicts_across_resource_types():
    with TestClient(app) as client:
        first = _create_case(client, **{"Idempotency-Key": "support-idem-01"})
        replay = _create_case(client, **{"Idempotency-Key": "support-idem-01"})
        conflict = client.post(
            "/api/v1/approvals",
            headers=_headers(**{"Idempotency-Key": "support-idem-01"}),
            json={
                "type": "refund",
                "reference_id": "ORD-2026-20055",
                "requested_by": "qa-suite",
                "amount": 800.0,
                "reason": "Cross-resource idempotency check",
            },
        )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == (
        "Idempotency-Key 'support-idem-01' was already used for support_case CASE-2026-10021 "
        "and cannot be reused for approval"
    )


def test_get_support_case_returns_404_for_other_group_and_unknown_case():
    with TestClient(app) as client:
        created = _create_case(client)
        case_id = created.json()["case_id"]
        other_group = client.get(f"/api/v1/support/cases/{case_id}", headers={"X-Lab-Group": "test-support-02"})
        unknown = client.get("/api/v1/support/cases/CASE-2026-9999", headers=_headers())

    assert created.status_code == 201
    assert other_group.status_code == 404
    assert other_group.json()["detail"] == "Support case not found"
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Support case not found"


def test_list_customer_support_cases_is_scoped_to_lab_group():
    with TestClient(app) as client:
        initial = client.get("/api/v1/customers/CUS-1001/support-cases", headers=_headers())
        created = _create_case(client)
        listed = client.get("/api/v1/customers/CUS-1001/support-cases", headers=_headers())

    assert initial.status_code == 200
    assert initial.json() == []
    assert created.status_code == 201
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["case_id"] == "CASE-2026-10021"
    assert items[0]["lab_group"] == LAB_GROUP
