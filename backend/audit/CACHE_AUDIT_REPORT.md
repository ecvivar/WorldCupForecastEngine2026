# DEPLOY-005: Cache Audit Report

**Cache service:** `RedisCacheService` via app core

---

## Hit/Miss & Latency by Endpoint

| Endpoint | 1st Call (ms) | 2nd Call (ms) | Speedup | Status |
|---------|-------------|--------------|--------|--------|
| teams:list | 70.26 | 8.5 | 8.3x | ✅ OK |
| teams:list (paginated) | 7.94 | 9.32 | 0.9x | ✅ OK |
| rankings:igf | 376.86 | 8.65 | 43.6x | ✅ OK |
| dashboard:main | 340.04 | 9.53 | 35.7x | ✅ OK |
| predictions:list | 287.74 | 8.44 | 34.1x | ✅ OK |
| matches:list | 30.56 | 12.16 | 2.5x | ✅ OK |
| simulations:list | 207.46 | 6.97 | 29.8x | ✅ OK |
| rankings:elo (paginated) | 19.99 | 7.39 | 2.7x | ✅ OK |
| rankings:fifa (paginated) | 18.16 | 5.78 | 3.1x | ✅ OK |

## PaginationParams Cache Key Stability

Keys stable across requests. ✅

## TTL Coverage

| Prefix | TTL (s) | Notes |
|--------|--------|-------|
| `benchmark:` | 1800 | |
| `calibration:` | 1800 | |
| `dashboard:` | 120 | |
| `groups:` | 300 | |
| `matches:` | 600 | |
| `predictions:` | 300 | |
| `probabilities:` | 300 | |
| `rankings:` | 300 | |
| `refinement:` | 1800 | |
| `simulations:` | 3600 | |
| `teams:` | 600 | |
| `(default)` | 300 | Fallback |

## Cache Invalidation Coverage

| Pattern | Trigger |
|--------|--------|
| `simulations:list:*` | Simulation create / run |
| `simulations:detail:{id}` | Simulation run |
| `dashboard:*` | Simulation run |
| `rankings:*` | Simulation run |
| `calibration:*` | Calibration adjustments apply |

**Missing:** teams, matches, groups, export, analysis endpoints

## Findings

| Severity | Issue |
|---------|-------|
| **Critical** | PaginationParams in cache keys (FIXED — added `__str__`) |
| **Critical** | Cached ORM objects produce invalid JSON on hit (FIXED — `jsonable_encoder` before cache set) |
| **High** | No invalidation on teams/matches mutations |
| **Medium** | POST endpoints cached (calibration) |
| **Medium** | Sync Redis calls in async endpoints |
| **Low** | `probabilities:` prefix unused |
| **Low** | No stampede protection |
