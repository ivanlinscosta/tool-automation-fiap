import re

from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-approvals-01"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


def _create_approval(client: TestClient, **header_overrides: str):
    return client.post(
        "/api/v1/approvals",
        headers=_headers(**header_overrides),
        json={
            "type": "refund",
            "reference_id": "ORD-2026-20001",
            "requested_by": "qa-suite",
            "amount": 650.0,
            "reason": "Customer refund requires review",
        },
    )


def test_create_approval_and_replay_idempotency():
    with TestClient(app) as client:
        first = _create_approval(client, **{"Idempotency-Key": "approval-idem-01"})
        replay = _create_approval(client, **{"Idempotency-Key": "approval-idem-01"})

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json() == {"approval_id": "APR-1011", "status": "pending"}
    assert replay.json() == first.json()


def test_create_approval_rejects_idempotency_key_reused_for_other_resource_type():
    with TestClient(app) as client:
        created = _create_approval(client, **{"Idempotency-Key": "approval-idem-02"})
        conflict = client.post(
            "/api/v1/support/cases",
            headers=_headers(**{"Idempotency-Key": "approval-idem-02"}),
            json={
                "customer_id": "CUS-1001",
                "category": "delivery",
                "summary": "Need update",
                "description": "Order has been delayed for several days.",
            },
        )

    assert created.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == (
        "Idempotency-Key 'approval-idem-02' was already used for approval APR-1011 "
        "and cannot be reused for support_case"
    )


def test_get_approval_detail_and_isolation():
    with TestClient(app) as client:
        created = _create_approval(client)
        approval_id = created.json()["approval_id"]
        detail = client.get(f"/api/v1/approvals/{approval_id}", headers=_headers())
        other_group = client.get(f"/api/v1/approvals/{approval_id}", headers={"X-Lab-Group": "test-approvals-02"})
        unknown = client.get("/api/v1/approvals/APR-9999", headers=_headers())

    assert created.status_code == 201
    assert re.fullmatch(r"APR-\d{4}", approval_id)
    assert detail.status_code == 200
    assert detail.json() == {
        "approval_id": approval_id,
        "type": "refund",
        "reference_id": "ORD-2026-20001",
        "requested_by": "qa-suite",
        "amount": 650.0,
        "reason": "Customer refund requires review",
        "status": "pending",
        "decision": None,
        "comment": None,
        "decided_by": None,
        "lab_group": LAB_GROUP,
        "created_at": detail.json()["created_at"],
        "decided_at": None,
    }
    assert other_group.status_code == 404
    assert other_group.json()["detail"] == "Approval not found"
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Approval not found"


def test_approval_decision_updates_detail_and_prevents_second_decision():
    with TestClient(app) as client:
        created = _create_approval(client)
        approval_id = created.json()["approval_id"]
        decided = client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            headers=_headers(),
            json={"decision": "approved", "comment": "Validated by supervisor"},
        )
        second_attempt = client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            headers=_headers(),
            json={"decision": "rejected", "comment": "Too late"},
        )

    assert created.status_code == 201
    assert decided.status_code == 200
    data = decided.json()
    assert data["approval_id"] == approval_id
    assert data["status"] == "approved"
    assert data["decision"] == "approved"
    assert data["comment"] == "Validated by supervisor"
    assert data["decided_by"] == "supervisor.ops@quantum.example"
    assert data["lab_group"] == LAB_GROUP
    assert data["decided_at"] is not None
    assert second_attempt.status_code == 409
    assert second_attempt.json()["detail"] == "Approval already decided"


def test_approval_decision_returns_404_for_other_group_or_unknown_id():
    with TestClient(app) as client:
        created = _create_approval(client)
        approval_id = created.json()["approval_id"]
        other_group = client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            headers={"X-Lab-Group": "test-approvals-02"},
            json={"decision": "approved", "comment": "Blocked by scope"},
        )
        unknown = client.post(
            "/api/v1/approvals/APR-9999/decision",
            headers=_headers(),
            json={"decision": "approved", "comment": "Missing approval"},
        )

    assert created.status_code == 201
    assert other_group.status_code == 404
    assert other_group.json()["detail"] == "Approval not found"
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Approval not found"


def test_approval_decision_rejects_missing_decision_field():
    with TestClient(app) as client:
        created = _create_approval(client)
        approval_id = created.json()["approval_id"]
        invalid = client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            headers=_headers(),
            json={"comment": "Decision field is required"},
        )

    assert created.status_code == 201
    assert invalid.status_code == 422
    error = invalid.json()["detail"]
    assert any(item["loc"][-1] == "decision" for item in error)
