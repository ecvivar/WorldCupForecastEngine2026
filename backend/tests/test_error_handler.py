from fastapi.testclient import TestClient

from app.core.exceptions import AppError, NotFoundError, ValidationError


class TestErrorHandler:
    def test_app_error_response(self, client: TestClient):
        resp = client.get("/api/v1/teams/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert "error" in body
        assert body["error"]["code"] == "HTTP_ERROR"
        assert body["error"]["message"] == "Team not found"

    def test_validation_error_format(self, client: TestClient):
        resp = client.post("/api/v1/teams", json={"invalid": "data"})
        # Should be 422 from FastAPI validation or 400 from our handler
        assert resp.status_code in (400, 422)
        body = resp.json()
        if "error" in body:
            assert body["error"]["code"] is not None

    def test_security_headers_present(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_content_security_policy(self, client: TestClient):
        resp = client.get("/health")
        assert "content-security-policy" in resp.headers
        csp = resp.headers["content-security-policy"]
        assert "default-src 'self'" in csp

    def test_strict_transport_security(self, client: TestClient):
        resp = client.get("/health")
        assert "strict-transport-security" in resp.headers
        assert "max-age=31536000" in resp.headers["strict-transport-security"]

    def test_cors_restricted(self, client: TestClient):
        resp = client.options(
            "/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # evil.com should not be in allowed origins
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert "evil.com" not in allow_origin
