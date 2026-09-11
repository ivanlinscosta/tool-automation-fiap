def _create_interaction(client, headers, payload):
    return client.post("/api/v1/interactions", headers=headers, json=payload)


def test_create_interaction(client, make_headers, interaction_payload):
    response = _create_interaction(client, make_headers(), interaction_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["interaction_id"].startswith("INT-")
    assert data["knowledge_articles"] == ["KB001"]


def test_list_interactions(client, make_headers, interaction_payload):
    _create_interaction(client, make_headers(student_id="grupo-01", request_id="req-int-1"), interaction_payload)
    _create_interaction(client, make_headers(student_id="grupo-02", request_id="req-int-2"), {**interaction_payload, "request_text": "Outro grupo"})

    response = client.get("/api/v1/interactions", headers=make_headers(student_id="grupo-01", request_id="req-int-list"))

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["lab_student_id"] == "grupo-01"


def test_get_interaction(client, make_headers, interaction_payload):
    created = _create_interaction(client, make_headers(), interaction_payload).json()

    response = client.get(f"/api/v1/interactions/{created['interaction_id']}", headers=make_headers(request_id="req-int-get"))

    assert response.status_code == 200
    assert response.json()["interaction_id"] == created["interaction_id"]
