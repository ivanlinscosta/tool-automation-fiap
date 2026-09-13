from fastapi.testclient import TestClient

from app.main import app


def _headers(lab_group: str | None = None, request_id: str = "req-001") -> dict[str, str]:
    headers = {"X-Request-ID": request_id}
    if lab_group is not None:
        headers["X-Lab-Group"] = lab_group
    return headers


def test_events_list_returns_seeded_system_events_for_anonymous_and_none_for_new_group():
    with TestClient(app) as client:
        anonymous_response = client.get(
            "/api/v1/events",
            headers=_headers(request_id="req-events-anonymous"),
        )

        assert anonymous_response.status_code == 200
        anonymous_events = anonymous_response.json()
        assert len(anonymous_events) == 5
        assert all(event["lab_group"] == "system" for event in anonymous_events)

        grouped_response = client.get(
            "/api/v1/events",
            headers=_headers("test-ev-01", "req-events-grouped"),
        )

        assert grouped_response.status_code == 200
        assert grouped_response.json() == []


def test_customer_lookup_creates_group_scoped_event_and_type_and_limit_filters_work():
    with TestClient(app) as client:
        lookup_response = client.get(
            "/api/v1/customers/CUS-1001",
            headers=_headers("test-ev-01", "req-events-customer-lookup"),
        )

        assert lookup_response.status_code == 200
        assert lookup_response.json()["id"] == "CUS-1001"

        events_response = client.get(
            "/api/v1/events?type=customer_lookup&limit=10",
            headers=_headers("test-ev-01", "req-events-type-filter"),
        )

        assert events_response.status_code == 200
        events = events_response.json()
        assert len(events) == 1

        event = events[0]
        assert set(event) >= {
            "event_id",
            "event_type",
            "lab_group",
            "customer_id",
            "timestamp",
            "resource_type",
            "resource_id",
        }
        assert event["event_type"] == "customer_lookup"
        assert event["lab_group"] == "test-ev-01"
        assert event["customer_id"] == "CUS-1001"
        assert event["resource_type"] == "customer"
        assert event["resource_id"] == "CUS-1001"

        limited_response = client.get(
            "/api/v1/events?type=customer_lookup&limit=1",
            headers=_headers("test-ev-01", "req-events-type-filter-limited"),
        )

        assert limited_response.status_code == 200
        assert len(limited_response.json()) == 1


def test_events_source_and_order_filters_read_metadata_json_fields():
    with TestClient(app) as client:
        source_response = client.get(
            "/api/v1/events?source=ai-agent",
            headers=_headers(request_id="req-events-source"),
        )

        assert source_response.status_code == 200
        source_events = source_response.json()
        assert len(source_events) == 3
        assert all('"source": "ai-agent"' in event["metadata_json"] for event in source_events)

        order_response = client.get(
            "/api/v1/events?order_id=ORD-2026-10001",
            headers=_headers(request_id="req-events-order-id"),
        )

        assert order_response.status_code == 200
        order_events = order_response.json()
        assert len(order_events) == 1
        assert order_events[0]["event_type"] == "shipment_lookup"
        assert order_events[0]["resource_id"] == "SHP-87421"
