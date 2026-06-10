# DEPLOY-002: Production Benchmark Report

**Date:** 2026-06-09
**Environment:** Docker Compose (PostgreSQL 5433, Redis 6379)
**Tool:** `benchmark_production.py` — 48 teams, 8 groups, 24 matches seeded

---

## Executive Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| API avg latency | 238.75 ms | <100 ms | FAIL |
| Engine avg latency | 121.38 ms | — | — |
| Match prediction | 9.29 ms | <20 ms | PASS |
| MC 1000 simulations | 28.55 ms | <50 ms | PASS |
| Cache avg improvement | 46.5% | — | — |

**Note:** The API target is dragged down by the Scenario Simulation POST
(1463 ms mean) and Full Predictions GET (240 ms). Excluding those two,
all lightweight endpoints average ~34 ms.

---

## API Endpoints (5 warmup samples each)

| Endpoint | Method | Mean (ms) | P50 (ms) | P95 (ms) | Min (ms) | Max (ms) |
|----------|--------|-----------|----------|----------|----------|----------|
| Health Check | GET | 7.12 | 5.74 | 12.62 | 5.63 | 12.62 |
| List Teams | GET | 22.56 | 14.16 | 56.51 | 13.66 | 56.51 |
| List Groups | GET | 10.40 | 10.12 | 11.36 | 9.91 | 11.36 |
| IGF Rankings | GET | 74.38 | 9.34 | 335.06 | 8.23 | 335.06 |
| Dashboard | GET | 74.21 | 13.57 | 318.15 | 11.74 | 318.15 |
| Full Predictions | GET | 240.43 | 235.67 | 253.11 | 231.56 | 253.11 |
| Match Calendar | GET | 17.00 | 16.84 | 18.05 | 16.03 | 18.05 |
| Scenario Simulation | POST | 1,463.88 | 248.86 | 3,894.47 | 248.30 | 3,894.47 |

> All endpoints returned HTTP 200 for every sample.

---

## Engine Operations (in-process, no HTTP)

| Operation | Mean (ms) | P50 (ms) | P95 (ms) | Peak Memory (MB) |
|-----------|-----------|----------|----------|------------------|
| Single Match Prediction | 9.29 | 9.08 | 10.77 | 0.02 |
| MC 100 simulations | 3.30 | 3.13 | 4.10 | 0.01 |
| MC 500 simulations | 15.74 | 14.92 | 18.22 | 0.01 |
| MC 1000 simulations | 28.55 | 28.68 | 28.80 | 0.01 |
| MC Engine 100 sims (serial) | 385.21 | 365.37 | 437.58 | 0.02 |
| Scenario (100 sims) | 286.17 | 284.95 | 291.22 | 0.01 |

> Memory footprint is negligible across all engine operations (0.01–0.02 MB peak).

---

## Cache Benchmarks (cold vs warm)

| Endpoint | Cold Mean (ms) | Warm Mean (ms) | Improvement |
|----------|---------------|---------------|-------------|
| Teams List | 15.48 | 14.67 | +5.2% |
| Groups List | 10.32 | 10.25 | +0.7% |
| IGF Rankings | 110.58 | 10.32 | +90.7% |
| Dashboard | 95.49 | 10.16 | +89.4% |

> Computationally heavy endpoints (IGF, Dashboard) benefit dramatically from
> Redis caching (>89% latency reduction). Light endpoints (Teams, Groups)
> show minimal improvement since the DB query itself is already fast.

---

## Target Verification

| Target | Expected | Actual | Result |
|--------|----------|--------|--------|
| `api_lt_100ms` | <100 ms | 238.75 ms | FAIL |
| `prediction_lt_20ms` | <20 ms | 9.29 ms | PASS |
| `mc_1000_lt_50ms` | <50 ms | 28.55 ms | PASS |

---

## Methodology

1. **Database:** PostgreSQL on `localhost:5433` via Docker Compose
2. **Cache:** Redis on `localhost:6379`, `decode_responses=True`, TTL per prefix
3. **Samples:** 5 per endpoint (3 for expensive POST), 3–5 per engine operation
4. **Cache benchmarks:** 3 cold requests → flush → 5 warm requests
5. **Seed data:** 48 teams, 8 groups (A–H), 24 completed matches
6. **Engine:** `MatchPredictionEngine.predict_full()` and `run_single_tournament_py()`
   with 48 `TeamEntity` objects at ~1500 ELO / 50.0 IGF
7. **Measurement:** `time.perf_counter()` wall-clock; `tracemalloc` for engine memory
