from fastapi.testclient import TestClient


class TestScenariosAPI:
    def test_scenarios_simulate_no_teams(self, client: TestClient):
        resp = client.post("/api/v1/scenarios/simulate", json={
            "modifications": [{"team_name": "Brazil", "result_modifier": 10}],
            "num_scenarios": 100,
        })
        assert resp.status_code == 400

    def test_scenarios_simulate(self, client: TestClient):
        client.post("/api/v1/teams", json={"name": "Brazil", "fifa_code": "BRA"})
        client.post("/api/v1/teams", json={"name": "Argentina", "fifa_code": "ARG"})
        client.post("/api/v1/teams", json={"name": "France", "fifa_code": "FRA"})
        resp = client.post("/api/v1/scenarios/simulate", json={
            "modifications": [
                {"team_name": "Brazil", "result_modifier": 10, "description": "10% stronger"},
            ],
            "num_scenarios": 100,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "scenario" in body
        assert "results" in body
        assert body["scenario"]["num_scenarios"] == 100
        assert len(body["scenario"]["modifications"]) == 1
        assert len(body["results"]) == 3
        assert body["results"][0]["team_name"] in ("Brazil", "Argentina", "France")
        assert 0 <= body["results"][0]["win_prob"] <= 100
