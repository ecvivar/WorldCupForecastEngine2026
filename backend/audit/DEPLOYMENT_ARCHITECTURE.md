# Deployment Architecture

**Date:** 2026-06-09
**Stack:** FastAPI · PostgreSQL (Neon) · Redis · Next.js (Vercel) · Docker
**Version:** 1.0.0
**Readiness:** 8.5/10 (Go for staging)
**Phase:** DEPLOY-001 — Production Environment Setup

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Internet                                  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Vercel (CDN + Edge)                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                   Next.js Frontend (SSR/SSG)                   │ │
│  │  /teams · /matches · /groups · /predictions · /simulations    │ │
│  │  /rankings · /calibration · /comparison · /scenarios · /export │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
└─────────────────────────────┼────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   Docker Host / Railway / Render                     │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    FastAPI Backend                             │    │
│  │  Port 8000 · Uvicorn · Gunicorn (multi-worker)               │    │
│  │                                                               │    │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐   │    │
│  │  │ Routers │ │ Services │ │ Engines  │ │ Middleware      │   │    │
│  │  │ 15 APIs │ │ 7 svcs   │ │ 6 mods   │ │ CORS · RateLimit│   │    │
│  │  └─────────┘ └──────────┘ └──────────┘ └────────────────┘   │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│                             │                                        │
│              ┌──────────────┼──────────────┐                        │
│              ▼              ▼              ▼                         │
│  ┌────────────────┐ ┌────────────┐ ┌──────────────┐                 │
│  │   PostgreSQL   │ │    Redis   │ │   Sentry     │                 │
│  │  (Neon-compat) │ │  (Cache)   │ │  (APM/Err)   │                 │
│  │  Pool: 10-20   │ │  TTL:2-60m │ │  Rate:0.1    │                 │
│  └────────────────┘ └────────────┘ └──────────────┘                 │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### FastAPI Backend (Container)

| Layer | Responsibility |
|-------|---------------|
| **Routers** (15) | HTTP request routing, input validation (Pydantic), response serialization |
| **Services** (7) | Business logic orchestration, cross-cutting concerns |
| **Engines** (6) | Core domain logic: IGF scoring, match prediction, Monte Carlo, calibration, scenario |
| **Middleware** | CORS, security headers, request logging, rate limiting, metrics, Prometheus |
| **Cache Decorator** | Transparent Redis caching with prefix-based TTL |
| **Auth/Security** | JWT (PyJWT), password hashing (pwdlib/Argon2), bearer token extraction |

### PostgreSQL Database (Neon)

| Purpose | Details |
|---------|---------|
| Primary store | Teams, matches, groups, standings, simulations, ELO ratings, FIFA rankings, xG metrics |
| Connection pooling | SQLAlchemy pool (size=10, max_overflow=20), pool_pre_ping=True |
| Migrations | Alembic (empty versions dir — tables created via `Base.metadata.create_all`) |
| Health check | `pg_isready` via Docker healthcheck |

### Redis Cache

| Purpose | Details |
|---------|---------|
| Response caching | 10 cache groups with prefix-based TTLs (2min-60min) |
| Patterns | Full-response caching via `@cached` decorator |
| Invalidation | Pattern-based SCAN + DEL |
| Fallback | All operations catch `RedisError` gracefully — app works without Redis |
| Persistence | RDB snapshots (configurable), AOF optional |

### Next.js Frontend (Vercel)

| Aspect | Details |
|--------|---------|
| Rendering | SSR + static generation (App Router) |
| Output | `standalone` mode for Docker |
| Pages | 18 static + 3 dynamic pages |
| API client | Typed fetch wrapper in `src/lib/api.ts` |
| Styling | Tailwind CSS, shadcn/ui, Radix primitives |

## Request Flow

```
1. Browser → Vercel Edge → Next.js SSR
2. Next.js calls FastAPI backend (NEXT_PUBLIC_API_URL)
3. FastAPI → Middleware stack:
   a. SecurityHeadersMiddleware (adds CSP, HSTS, etc.)
   b. MetricsMiddleware (counts requests, measures duration)
   c. RequestLogMiddleware (structured JSON logging)
   d. RateLimiter (slowapi — 5-10 req/min per endpoint)
4. FastAPI Router → Pydantic validation → Service → Engine
5. Service → SQLAlchemy ORM → PostgreSQL (pooled connection)
6. Service → Redis (if @cached decorator; fallback if Redis unavailable)
7. Response (JSON) → Middleware (response headers) → Client
```

## Cache Flow

```
┌──────────────┐     cache key?     ┌──────────────┐
│              │──────────────────▶│              │
│   Request    │  EXISTS in Redis  │   Redis      │
│              │◀──────────────────│              │
└──────────────┘     hit → return   └──────────────┘
       │ miss
       ▼
┌──────────────┐     compute +      ┌──────────────┐
│   Service    │──────────────────▶│   Redis      │
│  + Engine    │   SETEX (TTL)     │  Cache       │
└──────────────┘                   └──────────────┘
       │
       ▼
┌──────────────┐
│   Response   │
└──────────────┘

TTL Groups:
  rankings:, groups:, probabilities:, predictions:  → 300s (5min)
  calibration:, benchmark:, refinement:             → 1800s (30min)
  simulations:                                      → 3600s (60min)
  dashboard:                                        → 120s (2min)
  teams:, matches:                                  → 600s (10min)
```

## Docker Services

| Service | Image | Port | Health Check |
|---------|-------|------|-------------|
| db | postgres:16-alpine | 5432 | `pg_isready -U postgres` |
| redis | redis:7-alpine | 6379 | `redis-cli ping` |
| backend | custom (Dockerfile) | 8000 | `/health` endpoint |
| frontend | custom (Dockerfile) | 3000 | depends on backend |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string |
| `SECRET_KEY` | **Yes** | — | JWT signing key (min 32 chars) |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Allowed CORS origins |
| `SENTRY_DSN` | No | — | Sentry project DSN (optional) |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `NEXT_PUBLIC_API_URL` | Yes | — | Frontend → Backend API URL |
| `SENTRY_ENVIRONMENT` | No | `production` | Sentry environment tag |
| `DB_POOL_SIZE` | No | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | No | `20` | Max overflow connections |
| `CACHE_TTL` | No | `300` | Default Redis cache TTL (seconds) |
| `ENGINE_DEFAULT_SIMULATIONS` | No | `100000` | Default Monte Carlo simulation count |
| `DEBUG` | No | `false` | Debug mode (must be false in production) |

## Deployment Targets

| Component | Production | Staging | Local |
|-----------|-----------|---------|-------|
| Frontend | Vercel | Vercel preview | Docker/localhost:3000 |
| Backend | Docker/Railway/Render | Docker | Docker/localhost:8000 |
| Database | Neon | Neon | Docker/postgres:16 |
| Cache | Redis Cloud/Upstash | Docker | Docker/redis:7 |
| Monitoring | Sentry | Sentry (dev) | — |

---

## Production Docker Stack

### Quick Start

```bash
# 1. Configure environment
cp .env.production.example .env
# Edit .env with your production values

# 2. Start the stack
docker compose -f docker-compose.production.yml up -d

# 3. Monitor startup
docker compose -f docker-compose.production.yml logs -f

# 4. Verify health
curl http://localhost:8000/health
curl http://localhost:8000/health/database
curl http://localhost:8000/health/redis
curl http://localhost:8000/metrics
```

### Service Architecture

| Service | Container Name | Internal Port | Exposed Port | Health Check |
|---------|---------------|---------------|-------------|--------------|
| PostgreSQL | `wc2026-db` | 5432 | 127.0.0.1:5433 | `pg_isready -U postgres` |
| Redis | `wc2026-redis` | 6379 | 127.0.0.1:6379 | `redis-cli ping` |
| Backend | `wc2026-backend` | 8000 | 127.0.0.1:8000 | `/health` endpoint |
| Frontend | `wc2026-frontend` | 3000 | 127.0.0.1:3000 | depends on backend |

**Note:** All database and cache ports are bound to `127.0.0.1` only — not publicly accessible.

### Container Startup Sequence

```
1. PostgreSQL container starts → health check (pg_isready)
2. Redis container starts → health check (redis-cli ping)
3. Backend container starts (after db + redis healthy):
   a. docker-entrypoint.sh: wait for PostgreSQL
   b. Base.metadata.create_all() — create tables
   c. Seed data (idempotent — skips if competition exists)
   d. Numba warm-up — 3 mini-simulations to compile JIT
   e. Uvicorn starts on port 8000
4. Frontend container starts (after backend started):
   a. Node.js server on port 3000
   b. Connects to backend via NEXT_PUBLIC_API_URL
```

### Resource Limits

| Service | Memory Limit | Memory Reservation | CPU |
|---------|-------------|-------------------|-----|
| PostgreSQL | 512M | 256M | default |
| Redis | 256M | 128M | default |
| Backend | 1G | 512M | default |
| Frontend | 512M | 256M | default |

### Logging

All services use `json-file` logging driver with:
- Max file size: 10MB
- Max files: 3
- Rotation enabled

---

## Numba Warm-Up Strategy

### Problem
Numba `@njit` functions are compiled Just-In-Time on first invocation. Without warm-up, the first user request triggers JIT compilation, causing 2-10 second latency.

### Solution
The `app/core/warmup.py` module runs during container startup (in the `lifespan` context):

1. Creates 8 teams in 2 groups with synthetic strength scores
2. Calls `run_single_tournament_py()` 3 times
3. This triggers Numba JIT compilation for:
   - `simulate_group_stage_numba`
   - `rank_group_fifa`
   - `simulate_knockout_match`
   - `select_best_third_numba`
   - `run_knockout_round`
4. Warm-up is non-fatal — failure logs a warning but does not block startup

### Timing
- Expected warm-up duration: 5-15 seconds
- Logged as `Numba warm-up complete in Xms`
- Only runs once per container start
- Compiled functions remain cached in memory for the container lifetime

### Verification
```bash
docker compose -f docker-compose.production.yml logs backend | grep "warmup"
# Expected: "Numba warm-up: compiling JIT functions..."
# Expected: "Numba warm-up complete in 1234.5ms"
```

---

## Production Environment Variables

### File: `.env.production.example`

See `.env.production.example` at the project root for the complete template with documentation for every variable.

### Required Variables (MUST be set)

| Variable | Validation | How to Generate |
|----------|-----------|----------------|
| `DATABASE_URL` | Valid PostgreSQL connection string | Get from Neon dashboard |
| `SECRET_KEY` | Min 32 characters, unique per deployment | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | Valid URL(s), comma-separated | Set to frontend domain |

### Sensible Defaults

All other variables have safe defaults and are optional. See `.env.production.example` for the full list.

---

## Startup Readiness Validation

On every startup, the system validates:

1. **Database Connectivity** — `SELECT 1` query against PostgreSQL
2. **Redis Availability** — `redis-cli PING` (warning only, non-fatal)
3. **Secret Key** — Checks that `SECRET_KEY` is not the default value
4. **Numba Compilation** — Warm-up simulation (logged, non-fatal)

Results are logged via the `startup` logger in JSON format. Any errors cause the app to log them but continue running (degraded mode).
