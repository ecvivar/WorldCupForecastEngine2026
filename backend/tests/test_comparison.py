import uuid

from fastapi.testclient import TestClient


class TestComparisonAPI:
    def test_comparison_teams_not_found(self, client: TestClient):
        ta = uuid.uuid4()
        tb = uuid.uuid4()
        resp = client.get(f"/api/v1/comparison/teams/{ta}/{tb}")
        assert resp.status_code == 404

    def test_comparison_teams(self, client: TestClient):
        r1 = client.post("/api/v1/teams", json={"name": "Brazil", "fifa_code": "BRA", "continent": "South America"})
        r2 = client.post("/api/v1/teams", json={"name": "Argentina", "fifa_code": "ARG", "continent": "South America"})
        ta = r1.json()["id"]
        tb = r2.json()["id"]
        resp = client.get(f"/api/v1/comparison/teams/{ta}/{tb}")
        assert resp.status_code == 200
        body = resp.json()
        assert "team_a" in body
        assert "team_b" in body
        assert body["team_a"]["team_name"] == "Brazil"
        assert body["team_b"]["team_name"] == "Argentina"
        assert body["team_a"]["igf_score"] >= 0
        assert body["team_a"]["elo_score"] == 1500
