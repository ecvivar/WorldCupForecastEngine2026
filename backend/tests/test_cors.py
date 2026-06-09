from fastapi.testclient import TestClient

from app.core.config import get_settings


class TestCORS:
    def test_allowed_origin(self, client: TestClient):
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_disallowed_origin(self, client: TestClient):
        resp = client.get(
            "/health",
            headers={"Origin": "https://malicious-site.com"},
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin != "https://malicious-site.com"
        assert allow_origin == "" or allow_origin not in (
            "https://malicious-site.com",
            "*",
        )

    def test_wildcard_not_used(self, client: TestClient):
        resp = client.get("/health")
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin != "*"
