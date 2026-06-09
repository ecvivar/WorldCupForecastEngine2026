from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_root(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "timestamp" in body

    def test_health_database(self, client: TestClient):
        resp = client.get("/health/database")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "database" in body

    def test_health_redis(self, client: TestClient):
        resp = client.get("/health/redis")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "redis" in body

    def test_health_system(self, client: TestClient):
        resp = client.get("/health/system")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "python_version" in body
        assert "platform" in body

    def test_metrics(self, client: TestClient):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "http_requests_total" in text
        assert "http_active_requests" in text
        assert "cache_hits_total" in text
