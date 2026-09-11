EXPECTED_TEAM_FIELDS = {"category", "team", "email", "queue", "sla_default_hours"}
EXPECTED_TEAMS = {
    "it": "IT Support",
    "hr": "Human Resources",
    "finance": "Finance",
    "facilities": "Facilities",
    "security": "Security",
    "other": "General Support",
}


def test_get_team_it(client, make_headers):
    response = client.get("/api/v1/teams/it", headers=make_headers())

    assert response.status_code == 200, "IT team endpoint should return HTTP 200."
    assert response.json()["team"] == "IT Support", "IT category should resolve to the IT Support team."


def test_get_team_hr(client, make_headers):
    response = client.get("/api/v1/teams/hr", headers=make_headers(request_id="req-team-hr"))

    assert response.status_code == 200, "HR team endpoint should return HTTP 200."
    assert response.json()["team"] == "Human Resources", "HR category should resolve to the Human Resources team."


def test_get_team_all_categories(client, make_headers):
    for category, expected_team_name in EXPECTED_TEAMS.items():
        response = client.get(
            f"/api/v1/teams/{category}",
            headers=make_headers(request_id=f"req-team-{category}"),
        )
        assert response.status_code == 200, f"Category '{category}' should be available in seeded teams."
        assert response.json()["team"] == expected_team_name, f"Category '{category}' should route to the expected team."


def test_get_team_not_found(client, make_headers):
    response = client.get("/api/v1/teams/invalid", headers=make_headers(request_id="req-team-invalid"))

    assert response.status_code == 404, "Unknown team categories should return HTTP 404."
    assert response.json()["detail"] == "Team not found for category: invalid", "Unknown team responses should explain which category was missing."


def test_team_fields(client, make_headers):
    response = client.get("/api/v1/teams/security", headers=make_headers(request_id="req-team-fields"))

    assert response.status_code == 200, "Team field validation test should receive HTTP 200."
    data = response.json()
    assert EXPECTED_TEAM_FIELDS.issubset(data.keys()), "Team response should contain every expected field."
