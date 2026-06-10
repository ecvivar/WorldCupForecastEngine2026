# DEPLOY-004: Database Validation Audit Report

**Database:** PostgreSQL 16.14 on localhost:5433
**Pool:** `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`

---

## Table Sizes & Scan Statistics

| Table | Estimated Rows | Total Size | Seq Scans | Tuples Read by Seq Scan |
|-------|---------------|-----------|----------|------------------------|
| xg_metrics | ~0 | 24 kB | 0 | 0 |
| matches | ~0 | 88 kB | 10 | 216 |
| competitions | ~0 | 40 kB | 0 | 0 |
| group_standings | ~0 | 56 kB | 2 | 96 |
| teams | ~0 | 64 kB | 13 | 540 |
| simulations | ~0 | 24 kB | 2 | 0 |
| players | ~0 | 16 kB | 0 | 0 |
| elo_ratings | ~0 | 24 kB | 0 | 0 |
| simulation_results | ~0 | 24 kB | 0 | 0 |
| groups | ~0 | 40 kB | 7 | 56 |
| fifa_rankings | ~0 | 24 kB | 0 | 0 |

## Missing Indexes

No missing indexes detected on foreign keys.

## Endpoint Query Profile

| Endpoint | Method | Queries | Total Time (ms) | Slow (>50ms) | N+1? | Status |
|---------|--------|-------|---------------|-------------|------|--------|
| Health Check | GET | 0 | 0 | 0 | no | 200 |
| List Teams | GET | 1 | 7.23 | 0 | no | 200 |
| List Groups | GET | 1 | 4.33 | 0 | no | 200 |
| IGF Rankings | GET | 0 | 0 | 0 | no | 200 |
| Dashboard | GET | 0 | 0 | 0 | no | 200 |
| Full Predictions | GET | 101 | 312.39 | 0 | YES | 200 |
| Match Calendar | GET | 1 | 6.44 | 0 | no | 200 |
| Scenario Simulation | POST | 97 | 489.18 | 1 | YES | 200 |

### Health Check (`GET /health`)

- **Query count:** 0
- **Total query time:** 0ms
- **Slow queries (>50ms):** 0
- **N+1 detected:** No

### List Teams (`GET /api/v1/teams`)

- **Query count:** 1
- **Total query time:** 7.23ms
- **Slow queries (>50ms):** 0
- **N+1 detected:** No

### List Groups (`GET /api/v1/groups`)

- **Query count:** 1
- **Total query time:** 4.33ms
- **Slow queries (>50ms):** 0
- **N+1 detected:** No

### IGF Rankings (`GET /api/v1/rankings/igf`)

- **Query count:** 0
- **Total query time:** 0ms
- **Slow queries (>50ms):** 0
- **N+1 detected:** No

### Dashboard (`GET /api/v1/dashboard`)

- **Query count:** 0
- **Total query time:** 0ms
- **Slow queries (>50ms):** 0
- **N+1 detected:** No

### Full Predictions (`GET /api/v1/predictions`)

- **Query count:** 101
- **Total query time:** 312.39ms
- **Slow queries (>50ms):** 0
- **N+1 detected:** Yes
- **N+1 detail:** matches queried 21 times; teams queried 42 times; elo_ratings queried 40 times; xg_metrics queried 40 times

### Match Calendar (`GET /api/v1/matches`)

- **Query count:** 1
- **Total query time:** 6.44ms
- **Slow queries (>50ms):** 0
- **N+1 detected:** No

### Scenario Simulation (`POST /api/v1/scenarios/simulate`)

- **Query count:** 97
- **Total query time:** 489.18ms
- **Slow queries (>50ms):** 1
- **N+1 detected:** Yes
- **N+1 detail:** elo_ratings queried 48 times; group_standings queried 48 times; groups queried 48 times
- **Slow query details:**
  - `SELECT group_standings.id AS group_standings_id, group_standings.group_id AS group_standings_group_id, group_standings.team_id AS group_standings_team_id, group_standings.position AS group_standings_p` (161.42ms)

## N+1 Query Analysis

- **Full Predictions**: matches queried 21 times; teams queried 42 times; elo_ratings queried 40 times; xg_metrics queried 40 times
- **Scenario Simulation**: elo_ratings queried 48 times; group_standings queried 48 times; groups queried 48 times

## Connection Pooling

| Parameter | Current | Recommendation |
|----------|---------|---------------|
| `pool_size` | 10 | 20 for production (2× worker count) |
| `max_overflow` | 20 | 20 (keeps burst capacity) |
| `pool_pre_ping` | True | ✅ Good — prevents stale connections |
| `pool_recycle` | not set | Add 3600s for production |
| `max_connections` (DB) | 100 (default) | 200 for production |

## Transaction Handling

- **Scope:** Each request opens one session (via `get_db` dependency),
  commits on success, rolls back on error.
- **Auto-flush:** `False` — explicit flush required.
- **Auto-commit:** `False` — explicit commit required.
- **Assessment:** Correct for read-heavy workloads. OK.

## Optimization Opportunities

### High Priority

1. **Fix N+1 queries** — Use `joinedload()` or `selectinload()` in the
   following endpoints to eager-load relationships:
   - `Full Predictions`: matches queried 21 times; teams queried 42 times; elo_ratings queried 40 times; xg_metrics queried 40 times
   - `Scenario Simulation`: elo_ratings queried 48 times; group_standings queried 48 times; groups queried 48 times

### Medium Priority

- **Scenario Simulation** (97 queries, 489.18ms): Review query plan — consider adding composite indexes or materialized views.
### General Recommendations

1. **Add composite indexes** for common query patterns:
   - `(team_id, rating_date)` on `elo_ratings`, `fifa_rankings`, `xg_metrics`
     (covers 'latest for team' queries)
   - `(competition_id, stage)` on `matches`
     (covers match filtering by competition + stage)
   - `(competition_id, name)` on `groups`
     (covers group lookup within a competition)
2. **Add `pool_recycle=3600`** to prevent PostgreSQL from dropping
   idle connections after the default `tcp_keepalives_idle` timeout.
3. **Set `statement_timeout=30000`** on the production engine to
   kill runaway queries after 30 seconds.
