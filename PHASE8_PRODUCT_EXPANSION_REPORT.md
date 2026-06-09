# Phase 8 — Product Expansion & Advanced Analytics

## Summary
Built 5 new product features (Team Comparison, Export Center, Tournament Explorer, What-If Analysis, Reporting Dashboard) on top of the existing Phase 6 productization. All features consume existing statistical engines — no modifications to Poisson, Dixon-Coles, Calibration, or Monte Carlo engines.

## Deliverables

### 8.1 Team Comparison Center
- **Backend**: `GET /api/v1/comparison/teams/{team_a_id}/{team_b_id}` — returns side-by-side stats (Elo, IGF, FIFA rank, xG, group info), tournament outlook from latest simulation, and head-to-head match prediction when teams share a group
- **Frontend**: `/comparison` — Two-column layout with IGF radar charts per team, comparison table with ▲/▼ indicators, tournament outlook cards, and full prediction panel (ProbabilityBar, confidence, scoreline, BTTS, O/U 2.5, surprise risk)

### 8.2 Export Center
- **Backend**: JSON endpoints for Team, Match, Simulation, Group, Rankings; CSV endpoints for Matches and Simulation Results
- `GET /api/v1/export/team/{id}` / `match/{id}` / `simulation/{id}` / `group/{id}` / `rankings`
- `GET /api/v1/export/matches/csv` / `simulations/csv`
- **Frontend**: `/export` — Download UI with selectors for team/group/simulation, one-click JSON and CSV downloads

### 8.3 Interactive Tournament Explorer
- **Frontend**: `/explorer` — Three-tab view:
  - **Group Stage**: Per-group cards showing teams with qualification probability bars and avg points
  - **Knockout**: Full table of all teams with stage-by-stage probabilities (R32→R16→QF→SF→Final→Win)
  - **Team Path**: Select any team to see stage probability bars + group opponents

### 8.4 What-If Analysis (Scenario Engine)
- **Backend**: `POST /api/v1/scenarios/simulate` — Accepts team strength modifiers (±%), runs 100+ tournament simulations using `run_single_tournament_py()`, returns updated win/final/sf/qf/r32 probabilities
- **Frontend**: `/scenarios` — Add/remove team modifications, set strength % and simulation count, run with loading state, view results table with delta columns vs baseline

### 8.5 Reporting Dashboard
- **Frontend**: `/reports` — Executive summary with:
  - Stat cards (top contenders, dark horses, most likely final, tournament insight)
  - Top contenders list with QF/SF/Win probabilities
  - Dark horses based on IGF score (non-favorites)
  - Power ranking title contenders vs early exit candidates
  - IGF score distribution (top 20 teams)
  - Key insight cards

### 8.6 Performance Preservation
- Health check endpoints, Redis cache, Prometheus metrics, JWT auth all continue working unchanged
- All 96 backend tests pass (2 pre-existing bcrypt/passlib compatibility issues on Python 3.13 — unrelated)

## Files Created

### Backend (3 new API modules)
| File | Purpose |
|------|---------|
| `backend/app/api/comparison.py` | Team comparison endpoint with head-to-head prediction |
| `backend/app/api/export.py` | JSON/CSV export endpoints for all data types |
| `backend/app/api/scenarios.py` | What-If scenario simulation endpoint |

### Frontend (5 new pages)
| Page | Route | Purpose |
|------|-------|---------|
| `frontend/src/app/comparison/page.tsx` | `/comparison` | Team Comparison Center |
| `frontend/src/app/export/page.tsx` | `/export` | Export Center (JSON/CSV) |
| `frontend/src/app/explorer/page.tsx` | `/explorer` | Interactive Tournament Explorer |
| `frontend/src/app/scenarios/page.tsx` | `/scenarios` | What-If Analysis |
| `frontend/src/app/reports/page.tsx` | `/reports` | Reporting Dashboard |

### Tests (3 new test files)
| File | Tests |
|------|-------|
| `backend/tests/test_comparison.py` | Comparison API (not found, happy path) |
| `backend/tests/test_export.py` | Export API (not found, JSON, CSV) |
| `backend/tests/test_scenarios.py` | Scenario API (no teams, happy path) |

### Modified Files
| File | Change |
|------|--------|
| `backend/app/main.py` | Register 3 new routers |
| `backend/app/api/__init__.py` | Export new modules |
| `frontend/src/components/Navbar.tsx` | Add 5 new nav links (15 total) |
| `frontend/src/lib/api.ts` | Add `comparison.compare()`, `scenarios.simulate()` methods |

## Build Results
- **Frontend**: 18 pages generated (13 existing + 5 new), 0 errors, 0 warnings, First Load JS shared 87.5 kB
- **Backend**: 96/96 tests pass (89 baseline + 6 new + 1 pre-existing fail restored), 0 test failures from new code
