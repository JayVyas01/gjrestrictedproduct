def test_health_returns_ok(client, app_db):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_post(client, app_db):
    assert client.post("/api/health").status_code == 405


def test_security_headers_present(client, app_db):
    response = client.get("/api/health")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
