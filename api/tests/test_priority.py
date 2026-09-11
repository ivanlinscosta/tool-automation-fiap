def _post_priority(client, headers, impact, urgency, category="it", employee_id="EMP001"):
    return client.post(
        "/api/v1/priority/check",
        headers=headers,
        json={
            "employee_id": employee_id,
            "category": category,
            "impact": impact,
            "urgency": urgency,
        },
    )


def _assert_priority_result(response, priority, sla_hours, rule, requires_escalation):
    assert response.status_code == 200, "Priority calculation should succeed for valid impact/urgency combinations."
    data = response.json()
    assert data["priority"] == priority, f"Expected priority '{priority}' but received '{data['priority']}'."
    assert data["sla_hours"] == sla_hours, f"Expected SLA {sla_hours}h but received {data['sla_hours']}h."
    assert data["rule"] == rule, f"Expected rule '{rule}' but received '{data['rule']}'."
    assert data["requires_escalation"] is requires_escalation, "Escalation flag should match the computed priority severity."


def test_priority_low_low(client, make_headers):
    response = _post_priority(client, make_headers(), "low", "low")
    _assert_priority_result(response, "low", 24, "low_low_impact_urgency", False)


def test_priority_low_medium(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-low-medium"), "low", "medium")
    _assert_priority_result(response, "low", 12, "low_medium_impact_urgency", False)


def test_priority_low_high(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-low-high"), "low", "high")
    _assert_priority_result(response, "medium", 8, "low_high_impact_urgency", False)


def test_priority_medium_low(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-medium-low"), "medium", "low")
    _assert_priority_result(response, "low", 12, "medium_low_impact_urgency", False)


def test_priority_medium_medium(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-medium-medium"), "medium", "medium")
    _assert_priority_result(response, "medium", 6, "medium_medium_impact_urgency", False)


def test_priority_medium_high(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-medium-high"), "medium", "high")
    _assert_priority_result(response, "high", 4, "medium_high_impact_urgency", True)


def test_priority_high_low(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-high-low"), "high", "low")
    _assert_priority_result(response, "medium", 8, "high_low_impact_urgency", False)


def test_priority_high_medium(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-high-medium"), "high", "medium")
    _assert_priority_result(response, "high", 2, "high_medium_impact_urgency", True)


def test_priority_high_high(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-high-high"), "high", "high")
    _assert_priority_result(response, "critical", 1, "high_high_impact_urgency", True)


def test_security_override_low(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-security-low"), "low", "low", category="security")
    _assert_priority_result(response, "high", 4, "security_low_security_override", True)


def test_security_override_medium(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-security-medium"), "low", "medium", category="security")
    _assert_priority_result(response, "high", 2, "security_medium_security_override", True)


def test_security_override_high(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-security-high"), "low", "high", category="security")
    _assert_priority_result(response, "critical", 1, "security_high_security_override", True)


def test_priority_response_fields(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-priority-fields"), "medium", "medium")

    assert response.status_code == 200, "Priority field validation test should receive HTTP 200."
    data = response.json()
    assert {"priority", "sla_hours", "requires_escalation", "rule"}.issubset(data.keys()), "Priority response should contain every expected field."


def test_priority_requires_escalation(client, make_headers):
    high_response = _post_priority(client, make_headers(request_id="req-escalation-high"), "medium", "high")
    critical_response = _post_priority(client, make_headers(request_id="req-escalation-critical"), "high", "high")

    assert high_response.status_code == 200, "High-priority checks should succeed."
    assert critical_response.status_code == 200, "Critical-priority checks should succeed."
    assert high_response.json()["requires_escalation"] is True, "High-priority tickets should require escalation."
    assert critical_response.json()["requires_escalation"] is True, "Critical-priority tickets should require escalation."


def test_priority_sla_values(client, make_headers):
    expected_slas = {
        ("low", "low"): 24,
        ("low", "medium"): 12,
        ("low", "high"): 8,
        ("medium", "low"): 12,
        ("medium", "medium"): 6,
        ("medium", "high"): 4,
        ("high", "low"): 8,
        ("high", "medium"): 2,
        ("high", "high"): 1,
    }

    for (impact, urgency), expected_sla in expected_slas.items():
        response = _post_priority(
            client,
            make_headers(request_id=f"req-sla-{impact}-{urgency}"),
            impact,
            urgency,
        )
        assert response.status_code == 200, f"Priority request for {impact}/{urgency} should succeed."
        assert response.json()["sla_hours"] == expected_sla, f"Priority request for {impact}/{urgency} should map to the expected SLA."


def test_priority_invalid_impact(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-invalid-impact"), "urgent", "low")

    assert response.status_code == 422, "Invalid impact values should trigger FastAPI validation errors."


def test_priority_invalid_urgency(client, make_headers):
    response = _post_priority(client, make_headers(request_id="req-invalid-urgency"), "low", "urgent")

    assert response.status_code == 422, "Invalid urgency values should trigger FastAPI validation errors."
