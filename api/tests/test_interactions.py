from fastapi.testclient import TestClient

from app.main import app


def _headers(lab_group: str | None = None, request_id: str = "req-001") -> dict[str, str]:
    headers = {"X-Request-ID": request_id}
    if lab_group is not None:
        headers["X-Lab-Group"] = lab_group
    return headers


def _create_interaction(
    client: TestClient,
    *,
    lab_group: str,
    request_id: str,
    customer_id: str = "CUS-1001",
    channel: str = "chat",
    message: str = "Where is my order?",
    response: str = "We are tracking it now.",
    source: str = "ai-agent",
):
    return client.post(
        "/api/v1/interactions",
        headers=_headers(lab_group, request_id),
        json={
            "customer_id": customer_id,
            "channel": channel,
            "message": message,
            "response": response,
            "source": source,
        },
    )


def test_create_interaction_returns_next_seeded_id_and_persists_lab_group():
    with TestClient(app) as client:
        create_response = _create_interaction(
            client,
            lab_group="test-int-01",
            request_id="req-int-create",
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["interaction_id"] == "INT-10013"
        assert created["created_at"]

        get_response = client.get(
            f"/api/v1/interactions/{created['interaction_id']}",
            headers=_headers("test-int-01", "req-int-create-get"),
        )

        assert get_response.status_code == 200
        interaction = get_response.json()
        assert interaction["interaction_id"] == "INT-10013"
        assert interaction["lab_group"] == "test-int-01"
        assert interaction["customer_id"] == "CUS-1001"
        assert interaction["source"] == "ai-agent"


def test_list_interactions_respects_lab_group_customer_filter_limit_and_anonymous_access():
    with TestClient(app) as client:
        first = _create_interaction(
            client,
            lab_group="test-int-01",
            request_id="req-int-list-1",
            customer_id="CUS-1001",
            message="First message",
        )
        second = _create_interaction(
            client,
            lab_group="test-int-01",
            request_id="req-int-list-2",
            customer_id="CUS-1002",
            channel="email",
            message="Second message",
            response="Second response",
            source="n8n-workflow",
        )
        third = _create_interaction(
            client,
            lab_group="test-int-02",
            request_id="req-int-list-3",
            customer_id="CUS-1001",
            message="Other group message",
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 201

        grouped_response = client.get(
            "/api/v1/interactions",
            headers=_headers("test-int-01", "req-int-list-grouped"),
        )

        assert grouped_response.status_code == 200
        grouped_items = grouped_response.json()
        assert len(grouped_items) == 2
        assert {item["interaction_id"] for item in grouped_items} == {"INT-10013", "INT-10014"}
        assert all(item["lab_group"] == "test-int-01" for item in grouped_items)

        filtered_response = client.get(
            "/api/v1/interactions?customer_id=CUS-1002",
            headers=_headers("test-int-01", "req-int-list-filtered"),
        )

        assert filtered_response.status_code == 200
        filtered_items = filtered_response.json()
        assert len(filtered_items) == 1
        assert filtered_items[0]["interaction_id"] == "INT-10014"
        assert filtered_items[0]["customer_id"] == "CUS-1002"

        limited_response = client.get(
            "/api/v1/interactions?limit=1",
            headers=_headers("test-int-01", "req-int-list-limited"),
        )

        assert limited_response.status_code == 200
        limited_items = limited_response.json()
        assert len(limited_items) == 1
        assert limited_items[0]["interaction_id"] == "INT-10014"

        anonymous_response = client.get(
            "/api/v1/interactions",
            headers=_headers(request_id="req-int-list-anonymous"),
        )

        assert anonymous_response.status_code == 200
        anonymous_items = anonymous_response.json()
        assert len(anonymous_items) == 15
        assert any(item["interaction_id"] == "INT-10001" and item["lab_group"] == "system" for item in anonymous_items)


def test_get_interaction_enforces_lab_group_isolation_and_404_for_unknown_ids():
    with TestClient(app) as client:
        create_response = _create_interaction(
            client,
            lab_group="test-int-01",
            request_id="req-int-get-create",
            customer_id="CUS-1005",
        )

        assert create_response.status_code == 201
        interaction_id = create_response.json()["interaction_id"]

        anonymous_seed_response = client.get(
            "/api/v1/interactions/INT-10001",
            headers=_headers(request_id="req-int-seed-anonymous"),
        )
        assert anonymous_seed_response.status_code == 200
        assert anonymous_seed_response.json()["lab_group"] == "system"

        grouped_seed_response = client.get(
            "/api/v1/interactions/INT-10001",
            headers=_headers("test-int-01", "req-int-seed-grouped"),
        )
        assert grouped_seed_response.status_code == 404
        assert grouped_seed_response.json()["detail"] == "Interaction not found"

        grouped_created_response = client.get(
            f"/api/v1/interactions/{interaction_id}",
            headers=_headers("test-int-01", "req-int-created-grouped"),
        )
        assert grouped_created_response.status_code == 200
        assert grouped_created_response.json()["interaction_id"] == interaction_id

        unknown_response = client.get(
            "/api/v1/interactions/INT-99999",
            headers=_headers("test-int-01", "req-int-unknown"),
        )
        assert unknown_response.status_code == 404
        assert unknown_response.json()["detail"] == "Interaction not found"
