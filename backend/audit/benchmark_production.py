"""DEPLOY-002 — Production Benchmark with PostgreSQL + Redis."""

import json
import os
import sys
import time
import uuid

sys.path.insert(0, ".")

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5433/worldcup_forecast"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CACHE_ENABLED"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["SECRET_KEY"] = "prod-benchmark-secret-key-32-chars!!"

import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.models import (  # noqa: F401
    competition, elo_rating, fifa_ranking, group,
    group_standing, match, player, simulation, team, xg_metrics,
)
from app.db.session import Base
from app.core.dependencies import get_db, PaginationParams
from app.main import app
from app.engine.match_prediction import MatchPredictionConfig, MatchPredictionEngine
from app.engine.monte_carlo import run_single_tournament_py, MonteCarloEngine
from app.domain.entities import TeamEntity, SimulationConfig

# Set up PostgreSQL engine
_engine = create_engine(
    "postgresql+psycopg://postgres:postgres@localhost:5433/worldcup_forecast",
    pool_size=5, max_overflow=10,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)

def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

# Seed data: 48 teams + groups
def seed_data():
    db = TestingSessionLocal()
    try:
        # Check if data already seeded
        existing = db.execute(text("SELECT COUNT(*) FROM teams")).scalar()
        if existing and existing > 0:
            print(f"DB already has {existing} teams, skipping seed")
            return

        # Create competition
        from app.models.competition import Competition
        comp = Competition(id=uuid.uuid4(), name="FIFA World Cup 2026", season="2026")
        db.add(comp)
        db.flush()

        # Create teams
        team_ids = []
        team_names = [
            "Brazil", "Argentina", "France", "England", "Spain", "Germany",
            "Netherlands", "Portugal", "Belgium", "Italy", "Croatia", "Uruguay",
            "Colombia", "USA", "Mexico", "Japan", "South Korea", "Morocco",
            "Senegal", "Nigeria", "Ghana", "Cameroon", "Tunisia", "Algeria",
            "Egypt", "Ivory Coast", "Mali", "Burkina Faso", "South Africa", "DR Congo",
            "Australia", "Saudi Arabia", "Iran", "Qatar", "UAE", "Iraq",
            "Switzerland", "Denmark", "Sweden", "Poland", "Austria", "Czech Republic",
            "Turkey", "Ukraine", "Russia", "Wales", "Scotland", "Norway",
        ]
        fifa_codes = {
            "Brazil": "BRA", "Argentina": "ARG", "France": "FRA", "England": "ENG",
            "Spain": "ESP", "Germany": "GER", "Netherlands": "NED", "Portugal": "POR",
            "Belgium": "BEL", "Italy": "ITA", "Croatia": "CRO", "Uruguay": "URU",
            "Colombia": "COL", "USA": "USA", "Mexico": "MEX", "Japan": "JPN",
            "South Korea": "KOR", "Morocco": "MAR", "Senegal": "SEN", "Nigeria": "NGA",
            "Ghana": "GHA", "Cameroon": "CMR", "Tunisia": "TUN", "Algeria": "ALG",
            "Egypt": "EGY", "Ivory Coast": "CIV", "Mali": "MLI", "Burkina Faso": "BFA",
            "South Africa": "RSA", "DR Congo": "COD", "Australia": "AUS", "Saudi Arabia": "KSA",
            "Iran": "IRN", "Qatar": "QAT", "UAE": "UAE", "Iraq": "IRQ",
            "Switzerland": "SUI", "Denmark": "DEN", "Sweden": "SWE", "Poland": "POL",
            "Austria": "AUT", "Czech Republic": "CZE", "Turkey": "TUR", "Ukraine": "UKR",
            "Russia": "RUS", "Wales": "WAL", "Scotland": "SCO", "Norway": "NOR",
        }
        for name in team_names:
            t = team.Team(
                id=uuid.uuid4(), name=name, fifa_code=fifa_codes[name],
                continent="Europe", is_national_team=True,
            )
            db.add(t)
            team_ids.append(t.id)
        db.flush()

        # Create groups A-H
        group_ids = []
        for g in "ABCDEFGH":
            grp = group.Group(id=uuid.uuid4(), competition_id=comp.id, name=f"Group {g}", stage="group")
            db.add(grp)
            group_ids.append(grp.id)
        db.flush()

        # Create group standings
        for i, tid in enumerate(team_ids[:48]):
            gs = group_standing.GroupStanding(
                id=uuid.uuid4(), group_id=group_ids[i % 8], team_id=tid,
                position=(i % 6) + 1, played=3, won=2 - (i % 3), drawn=1, lost=(i % 2),
                goals_for=5 - (i % 4), goals_against=3 - (i % 3),
                goal_difference=2 + (i % 3), points=7 - (i % 2), qualified=(i % 6) < 4,
            )
            db.add(gs)

        # Create some matches
        for i in range(0, 48, 2):
            if i + 1 >= len(team_ids):
                break
            m = match.Match(
                id=uuid.uuid4(), competition_id=comp.id,
                home_team_id=team_ids[i], away_team_id=team_ids[i + 1],
                match_date="2026-06-09", stage="group",
                group_name=f"Group {chr(65 + (i // 6) % 8)}",
                home_goals=(i % 3), away_goals=(i % 2),
                home_xg=1.5 + (i % 3) * 0.5, away_xg=1.0 + (i % 2) * 0.5,
                is_neutral_venue=False, status="completed",
            )
            db.add(m)

        db.commit()
        print(f"Seeded {len(team_ids)} teams, 8 groups, 24 matches")
    finally:
        db.close()

seed_data()


def measure(method: str, path: str, label: str, n: int = 5, json_body: dict | None = None) -> dict:
    latencies = []
    statuses = []
    for _ in range(n):
        start = time.perf_counter()
        if json_body:
            resp = client.post(path, json=json_body)
        else:
            resp = client.get(path)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        statuses.append(resp.status_code)
    latencies.sort()
    return {
        "label": label, "method": method, "path": path,
        "mean_ms": round(np.mean(latencies), 2),
        "p50_ms": round(np.median(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
        "p99_ms": round(latencies[-1], 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "statuses": list(set(statuses)),
        "samples": n,
    }


def measure_engine(label: str, fn, n: int = 5) -> dict:
    import tracemalloc
    latencies = []
    tracemalloc.start()
    for _ in range(n):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    latencies.sort()
    return {
        "label": label,
        "mean_ms": round(np.mean(latencies), 2),
        "p50_ms": round(np.median(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
        "max_ms": round(max(latencies), 2),
        "peak_memory_mb": round(peak / (1024 * 1024), 2),
        "samples": n,
    }


def cache_benchmark(path: str, label: str) -> dict:
    """Measure cold (no cache) vs warm (cached) request."""
    # Flush cache for cold measurement
    from app.core.cache import get_cache
    try:
        get_cache().flush_all()
    except Exception:
        pass

    cold_times = []
    for _ in range(3):
        start = time.perf_counter()
        client.get(path)
        cold_times.append((time.perf_counter() - start) * 1000)

    warm_times = []
    for _ in range(5):
        start = time.perf_counter()
        client.get(path)
        warm_times.append((time.perf_counter() - start) * 1000)

    cold_avg = round(np.mean(cold_times), 2)
    warm_avg = round(np.mean(warm_times), 2)
    improvement = round((cold_avg - warm_avg) / cold_avg * 100, 1) if cold_avg > 0 else 0

    return {
        "label": f"Cache: {label}",
        "path": path,
        "cold_mean_ms": cold_avg,
        "warm_mean_ms": warm_avg,
        "improvement_pct": improvement,
    }


def main():
    # Flush any stale cache from previous runs
    from app.core.cache import get_cache
    try:
        get_cache().flush_all()
    except Exception:
        pass

    results = {
        "api_endpoints": [],
        "engine_operations": [],
        "cache_benchmarks": [],
        "summary": {},
    }

    # === API Endpoints ===
    endpoints = [
        ("GET", "/health", "Health Check"),
        ("GET", "/api/v1/teams", "List Teams"),
        ("GET", "/api/v1/groups", "List Groups"),
        ("GET", "/api/v1/rankings/igf", "IGF Rankings"),
        ("GET", "/api/v1/dashboard", "Dashboard"),
        ("GET", "/api/v1/predictions", "Full Predictions"),
        ("GET", "/api/v1/matches", "Match Calendar"),
    ]
    for method, path, label in endpoints:
        results["api_endpoints"].append(measure(method, path, label))

    # Scenario simulation (POST)
    results["api_endpoints"].append(measure("POST", "/api/v1/scenarios/simulate",
        "Scenario Simulation", n=3,
        json_body={"modifications": [], "num_scenarios": 100}))

    # === Engine Operations ===
    teams_list = [
        TeamEntity(id=i, name=f"Team {i}", elo_score=1500 + (i % 5) * 100, igf_score=50.0 + (i % 10) * 5)
        for i in range(48)
    ]
    group_mapping = {t.id: chr(65 + (i % 12)) for i, t in enumerate(teams_list)}
    strengths = np.array([t.igf_score / 50.0 for t in teams_list], dtype=np.float64)
    assignments = np.array([ord(group_mapping[t.id]) - 65 for t in teams_list], dtype=np.int64)

    mp_engine = MatchPredictionEngine(config=MatchPredictionConfig())
    home, away = teams_list[0], teams_list[1]

    def predict_match():
        mp_engine.predict_full(home, away, home_advantage=True)

    results["engine_operations"].append(measure_engine("Single Match Prediction", predict_match))

    for n_sims, label in [(100, "MC 100 simulations"), (500, "MC 500 simulations"), (1000, "MC 1000 simulations")]:
        reps = n_sims // 100
        def mc_run(reps=reps):
            for _ in range(reps):
                run_single_tournament_py(strengths, assignments, 48)
        results["engine_operations"].append(measure_engine(label, mc_run, n=3 if n_sims > 100 else 5))

    # MC Engine (serial, 100 sims)
    mc_engine = MonteCarloEngine(config=SimulationConfig(num_simulations=100, parallel=False))
    def mc_engine_run():
        mc_engine.run(teams_list, group_mapping)
    results["engine_operations"].append(measure_engine("MC Engine 100 sims (serial)", mc_engine_run, n=3))

    # Scenario simulation (engine level)
    def scenario_run():
        for _ in range(100):
            run_single_tournament_py(strengths, assignments, 48)
    results["engine_operations"].append(measure_engine("Scenario (100 sims)", scenario_run, n=3))

    # === Cache Benchmarks ===
    for path, label in [
        ("/api/v1/teams", "Teams List"),
        ("/api/v1/groups", "Groups List"),
        ("/api/v1/rankings/igf", "IGF Rankings"),
        ("/api/v1/dashboard", "Dashboard"),
    ]:
        results["cache_benchmarks"].append(cache_benchmark(path, label))

    # === Summary ===
    api_means = [r["mean_ms"] for r in results["api_endpoints"]]
    engine_means = [r["mean_ms"] for r in results["engine_operations"]]
    cache_improvements = [r["improvement_pct"] for r in results["cache_benchmarks"]]

    target_map = {
        "api_lt_100ms": "api_avg_ms",
        "prediction_lt_20ms": "prediction_ms",
        "mc_1000_lt_50ms": "mc_1000_ms",
    }
    results["summary"] = {
        "api_avg_ms": round(float(np.mean(api_means)), 2),
        "api_p95_max_ms": float(max(r["p95_ms"] for r in results["api_endpoints"])),
        "engine_avg_ms": round(float(np.mean(engine_means)), 2),
        "prediction_ms": float(results["engine_operations"][0]["mean_ms"]),
        "mc_1000_ms": float(results["engine_operations"][3]["mean_ms"]),
        "mc_engine_100_ms": float(results["engine_operations"][4]["mean_ms"]),
        "cache_avg_improvement_pct": round(float(np.mean(cache_improvements)), 1),
        "targets": {
            "api_lt_100ms": bool(all(r["mean_ms"] < 100 for r in results["api_endpoints"])),
            "prediction_lt_20ms": bool(results["engine_operations"][0]["mean_ms"] < 20),
            "mc_1000_lt_50ms": bool(results["engine_operations"][3]["mean_ms"] < 50),
        },
    }

    print(json.dumps(results, indent=2, default=str))
    with open("audit/PRODUCTION_BENCHMARK.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nSaved to audit/PRODUCTION_BENCHMARK.json")

    # Print targets
    print("\n=== TARGET CHECK ===")
    for k, v in results["summary"]["targets"].items():
        metric_key = target_map.get(k, k)
        val = results["summary"].get(metric_key, "?")
        print(f"  {k}: {'PASS' if v else 'FAIL'} ({val}ms)")


if __name__ == "__main__":
    main()
