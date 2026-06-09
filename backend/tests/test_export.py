import uuid

from fastapi.testclient import TestClient


class TestExportAPI:
    def test_export_team_not_found(self, client: TestClient):
        resp = client.get(f"/api/v1/export/team/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_export_match_not_found(self, client: TestClient):
        resp = client.get(f"/api/v1/export/match/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_export_group_not_found(self, client: TestClient):
        resp = client.get(f"/api/v1/export/group/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_export_matches_csv(self, client: TestClient):
        resp = client.get("/api/v1/export/matches/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]

    def test_export_simulations_csv(self, client: TestClient):
        resp = client.get("/api/v1/export/simulations/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
