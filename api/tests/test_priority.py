def _post_priority(client, headers, impact, urgency, category="technology", student_id="STU001"):
    return client.post(
        "/api/v1/priority/check",
        headers=headers,
        json={
            "student_id": student_id,
            "category": category,
            "impact": impact,
            "urgency": urgency,
        },
    )


def _assert_priority_result(response, priority, sla_hours, rule, requires_escalation):
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == priority
    assert data["sla_hours"] == sla_hours
    assert data["rule"] == rule
    assert data["requires_escalation"] is requires_escalation


def test_priority_low_low(client, make_headers):
    _assert_priority_result(_post_priority(client, make_headers(), "low", "low"), "low", 24, "low_low_impact_urgency", False)


def test_priority_medium_high(client, make_headers):
    _assert_priority_result(_post_priority(client, make_headers(), "medium", "high"), "high", 4, "medium_high_impact_urgency", True)


def test_priority_high_high(client, make_headers):
    _assert_priority_result(_post_priority(client, make_headers(), "high", "high"), "critical", 1, "high_high_impact_urgency", True)


def test_campus_access_override_low(client, make_headers):
    _assert_priority_result(_post_priority(client, make_headers(), "low", "low", category="campus_access"), "high", 4, "campus_access_low_campus_access_override", True)


def test_campus_access_override_high(client, make_headers):
    _assert_priority_result(_post_priority(client, make_headers(), "low", "high", category="campus_access"), "critical", 1, "campus_access_high_campus_access_override", True)


def test_priority_invalid_impact(client, make_headers):
    response = _post_priority(client, make_headers(), "urgent", "low")
    assert response.status_code == 422
