def test_list_knowledge_articles(client, make_headers):
    response = client.get("/api/v1/knowledge", headers=make_headers())

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 30
    assert all("Conteúdo fictício para fins didáticos." in item["content"] for item in data)


def test_list_knowledge_by_category(client, make_headers):
    response = client.get("/api/v1/knowledge?category=library", headers=make_headers(request_id="req-kb-library"))

    assert response.status_code == 200
    assert all(item["category"] == "library" for item in response.json())


def test_search_knowledge(client, make_headers):
    response = client.get("/api/v1/knowledge/search?q=wifi conexão&category=technology", headers=make_headers(request_id="req-kb-search"))

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "wifi conexão"
    assert len(data["results"]) >= 1
    assert data["results"][0]["id"] == "KB006"


def test_get_knowledge_article(client, make_headers):
    response = client.get("/api/v1/knowledge/KB001", headers=make_headers(request_id="req-kb-get"))

    assert response.status_code == 200
    assert response.json()["id"] == "KB001"
