# Deployment Validation Checklist

**Date:** 2026-06-09
**Phase:** DEPLOY-001 — Production Environment Setup
**Target Stack:** PostgreSQL (Neon) · Redis · FastAPI · Next.js · Docker

---

## 1. Environment Configuration

- [ ] `.env.production.example` documents all required variables
- [ ] `DATABASE_URL` points to Neon PostgreSQL (or production equivalent)
- [ ] `SECRET_KEY` is set to a strong random value (min 32 chars)
- [ ] `CORS_ORIGINS` set to the actual frontend domain(s)
- [ ] `SENTRY_DSN` configured for error tracking
- [ ] `REDIS_URL` points to production Redis instance
- [ ] `LOG_LEVEL` set to `INFO` (not `DEBUG`)
- [ ] `DEBUG=false` in production
- [ ] JWT configuration matches security requirements

## 2. Docker Stack Build

- [ ] `backend/Dockerfile` builds without errors
- [ ] `frontend/Dockerfile` builds without errors
- [ ] `docker-compose.production.yml` parses without syntax errors
- [ ] Backend image size is reasonable (< 1GB)
- [ ] Frontend image builds with `standalone` output
- [ ] No security vulnerabilities in base images

## 3. Service Health

- [ ] PostgreSQL container starts and passes `pg_isready`
- [ ] Redis container starts and passes `redis-cli ping`
- [ ] Backend container starts without errors
- [ ] Backend health endpoint returns `{"status": "ok"}`
- [ ] `/health/database` reports connected
- [ ] `/health/redis` reports connected
- [ ] `/health/system` returns platform info
- [ ] Frontend container starts without errors
- [ ] Frontend serves pages without 500 errors

## 4. Database Initialization

- [ ] Tables created (`Base.metadata.create_all` succeeds)
- [ ] Seed script runs without errors
- [ ] 48 teams seeded across 12 groups
- [ ] 72 group matches created
- [ ] Competition record exists
- [ ] Group standings initialized
- [ ] ELO ratings populated
- [ ] FIFA rankings populated
- [ ] xG metrics populated

## 5. Startup Validation

- [ ] Startup readiness report logged at INFO level
- [ ] No startup errors in logs
- [ ] Sentry SDK initialized (if DSN configured)
- [ ] Prometheus `/metrics` endpoint responds
- [ ] Prometheus business counters initialized (predictions, simulations, scenarios, calibrations)
- [ ] Rate limiter active (slowapi)
- [ ] Security headers present (X-Frame-Options, CSP, HSTS)
- [ ] Request logging structured (JSON format)

## 6. Numba Warm-Up

- [ ] Warm-up runs during container startup
- [ ] Numba JIT compilation logged with timing
- [ ] Warm-up completes within 30 seconds
- [ ] First prediction request does not trigger JIT compilation
- [ ] Warm-up failure does not crash the container (non-fatal)

## 7. Cache & Redis

- [ ] Redis responds to ping from backend container
- [ ] Cache TTL configuration loaded
- [ ] Cache decorator operational (read/write)
- [ ] Cache invalidation works (pattern-based SCAN + DEL)
- [ ] Redis persistence configured (AOF or RDB)

## 8. Security

- [ ] Backend port 8000 not exposed to public internet directly
- [ ] PostgreSQL port 5433 not exposed to public internet
- [ ] Redis port 6379 not exposed to public internet
- [ ] CORS restricted to specific origins (not `*`)
- [ ] CSP headers restrict script sources
- [ ] HSTS enabled with `includeSubDomains`
- [ ] Non-root user runs the backend container

## 9. Networking

- [ ] Backend can reach PostgreSQL (internal Docker network)
- [ ] Backend can reach Redis (internal Docker network)
- [ ] Frontend can reach Backend API
- [ ] Health check dependencies respected (depends_on conditions)

## 10. Logging & Monitoring

- [ ] JSON structured logging enabled
- [ ] Log levels correctly applied
- [ ] Request ID propagated through logs
- [ ] Container logs accessible via `docker compose logs`
- [ ] Log rotation configured (max-size 10m, max-file 3)

---

## Validation Summary

| Check | Status | Notes |
|-------|--------|-------|
| Docker Build | ❓ | |
| DB Connectivity | ❓ | |
| Redis Connectivity | ❓ | |
| Seed Data | ❓ | |
| Numba Warm-Up | ❓ | |
| Health Endpoints | ❓ | |
| Prometheus Metrics | ❓ | |
| Security Headers | ❓ | |

**Overall Status:** ❓ PENDING

**Next Step:** DEPLOY-002 — Production Benchmark
