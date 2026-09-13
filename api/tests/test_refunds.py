from fastapi.testclient import TestClient

from app.main import app


LAB_GROUP = "test-refunds-01"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


def _create_refund(client: TestClient, payload: dict, headers: dict[str, str] | None = None):
    return client.post("/api/v1/refunds", headers=headers or _headers(), json=payload)


def _create_approval(client: TestClient, amount: float, group: str = LAB_GROUP):
    return client.post(
        "/api/v1/approvals",
        headers={"X-Lab-Group": group},
        json={
            "type": "refund",
            "reference_id": "ORD-2026-30001",
            "requested_by": "refund-suite",
            "amount": amount,
            "reason": "Approval requested for high-value refund",
        },
    )


def test_create_low_value_refund_without_approval():
    with TestClient(app) as client:
        response = _create_refund(
            client,
            {"order_id": "ORD-2026-20010", "amount": 150.0, "reason": "delivery_issue"},
        )

    assert response.status_code == 201
    assert response.json() == {"refund_id": "REF-10007", "status": "processing", "amount": 150.0}


def test_high_value_refund_requires_approved_approval():
    with TestClient(app) as client:
        response = _create_refund(
            client,
            {"order_id": "ORD-2026-20011", "amount": 7899.8, "reason": "delivery_issue"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Refunds above R$500.00 require an approved approval"


def test_high_value_refund_rejects_pending_approval():
    with TestClient(app) as client:
        created_approval = _create_approval(client, amount=8000.0)
        approval_id = created_approval.json()["approval_id"]
        response = _create_refund(
            client,
            {
                "order_id": "ORD-2026-20012",
                "amount": 7899.8,
                "reason": "delivery_issue",
                "approval_id": approval_id,
            },
        )

    assert created_approval.status_code == 201
    assert approval_id == "APR-1011"
    assert response.status_code == 400
    assert response.json()["detail"] == "Refunds above R$500.00 require an approved approval"


def test_high_value_refund_succeeds_after_approval_is_approved():
    with TestClient(app) as client:
        created_approval = _create_approval(client, amount=8000.0)
        approval_id = created_approval.json()["approval_id"]
        decided = client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            headers=_headers(),
            json={"decision": "approved", "comment": "Refund approved"},
        )
        created_refund = _create_refund(
            client,
            {
                "order_id": "ORD-2026-20013",
                "amount": 7899.8,
                "reason": "delivery_issue",
                "approval_id": approval_id,
            },
        )
        refund_id = created_refund.json()["refund_id"]
        detail = client.get(f"/api/v1/refunds/{refund_id}", headers=_headers())
        other_group = client.get(f"/api/v1/refunds/{refund_id}", headers={"X-Lab-Group": "test-refunds-02"})

    assert created_approval.status_code == 201
    assert decided.status_code == 200
    assert created_refund.status_code == 201
    assert created_refund.json() == {"refund_id": "REF-10007", "status": "processing", "amount": 7899.8}
    assert detail.status_code == 200
    assert detail.json() == {
        "refund_id": "REF-10007",
        "order_id": "ORD-2026-20013",
        "amount": 7899.8,
        "reason": "delivery_issue",
        "approval_id": approval_id,
        "status": "processing",
        "lab_group": LAB_GROUP,
        "created_at": detail.json()["created_at"],
    }
    assert other_group.status_code == 404
    assert other_group.json()["detail"] == "Refund not found"


def test_high_value_refund_rejects_approval_from_another_lab_group():
    with TestClient(app) as client:
        foreign_approval = _create_approval(client, amount=8000.0, group="test-refunds-02")
        foreign_approval_id = foreign_approval.json()["approval_id"]
        client.post(
            f"/api/v1/approvals/{foreign_approval_id}/decision",
            headers={"X-Lab-Group": "test-refunds-02"},
            json={"decision": "approved", "comment": "Approved elsewhere"},
        )
        response = _create_refund(
            client,
            {
                "order_id": "ORD-2026-20014",
                "amount": 7899.8,
                "reason": "delivery_issue",
                "approval_id": foreign_approval_id,
            },
        )

    assert foreign_approval.status_code == 201
    assert response.status_code == 400
    assert response.json()["detail"] == "Refunds above R$500.00 require an approved approval"


def test_get_refund_returns_404_for_unknown_or_other_group():
    with TestClient(app) as client:
        other_group = client.get("/api/v1/refunds/REF-10005", headers=_headers())
        unknown = client.get("/api/v1/refunds/REF-99999", headers=_headers())

    assert other_group.status_code == 404
    assert other_group.json()["detail"] == "Refund not found"
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Refund not found"
