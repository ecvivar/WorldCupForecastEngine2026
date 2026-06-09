PHASE 9.5 — Production Hardening & Launch Readiness
Context

We have completed:

Core forecasting engine
Monte Carlo simulation engine
Poisson + Dixon-Coles + Bayesian prediction pipeline
Calibration Engine
Calibration Refinement Engine
Scenario Engine
Product features (comparison, explorer, reports, exports)
Frontend platform
Security review
Performance review
Data quality review
Observability review
Technical debt review
Production readiness review

Current status:

READY FOR STAGING
READY FOR PUBLIC BETA AFTER MINOR FIXES

The goal of this phase is NOT to add new forecasting features.

The goal is to eliminate production blockers and improve operational maturity.

PRIORITY 1 — SECURITY HARDENING
SEC-001 Secret Key Validation

Current issue:

secret_key = "change-me-me-in-production"

Implement startup validation.

Requirements:

Application must refuse startup when default secret is detected
Clear error message
Validation through pydantic-settings
Support local development via .env

Expected result:

RuntimeError:
SECRET_KEY must be configured before deployment
SEC-002 Global API Rate Limiting

Implement HTTP rate limiting.

Suggested stack:

slowapi

Requirements:

Anonymous endpoints
100 req/minute
Expensive endpoints
simulation/*
scenarios/*
predictions/*

Limit:

20 req/minute
Auth endpoints
10 req/minute

Return:

429 Too Many Requests

Include tests.

SEC-003 JWT Modernization

Replace:

python-jose

with:

PyJWT

Requirements:

Preserve current API
Preserve token format
Preserve refresh flow
Update tests
PRIORITY 2 — OBSERVABILITY
OBS-001 Sentry Integration

Integrate:

sentry-sdk

Requirements:

FastAPI integration
Capture unhandled exceptions
Capture request context
Capture user context when available
Environment-aware configuration

Environment variables:

SENTRY_DSN=
SENTRY_ENVIRONMENT=

Disabled automatically if DSN absent.

OBS-002 Startup Health Validation

Before application starts:

Validate:

Database connection
Redis connection (optional warning)
Required environment variables

Create:

StartupReadinessReport

Log structured summary.

OBS-003 Prometheus Readiness

Review current metrics implementation.

Goals:

Ensure Prometheus compatibility
Persist useful counters
Add:
prediction_requests_total
simulation_runs_total
scenario_runs_total
calibration_runs_total

Expose through existing:

/metrics
PRIORITY 3 — QUALITY IMPROVEMENTS
QA-001 Calibration Test Stabilization

Current state:

Several calibration tests fail because prediction pipelines are not initialized correctly.

Requirements:

Fix all failing calibration tests
Use realistic mock prediction outputs
Ensure deterministic results

Target:

100% calibration suite passing
QA-002 Password Hashing Compatibility

Current issue:

passlib + bcrypt incompatibility

Requirements:

Choose one:

Option A

Pin supported bcrypt version

Option B

Migrate to pwdlib

Preferred:

pwdlib

Update authentication service and tests.

QA-003 Coverage Reporting

Add:

pytest-cov

Generate:

coverage html
coverage xml

CI must fail if coverage drops below:

80%
PRIORITY 4 — MODERNIZATION
MOD-001 FastAPI Lifespan Pattern

Replace:

@app.on_event("startup")
@app.on_event("shutdown")

with:

lifespan()

Requirements:

Preserve all startup behavior
Preserve shutdown cleanup
Add tests
MOD-002 Pydantic Warnings Cleanup

Resolve:

model_name protected namespace warning

Requirements:

No warnings during:

pytest
uvicorn startup
PRIORITY 5 — DEPLOYMENT VALIDATION
DEPLOY-001 Production Stack Benchmark

Create benchmark script using:

PostgreSQL
Redis

instead of SQLite.

Measure:

Health endpoint
Rankings
Dashboard
Full prediction
Monte Carlo simulations

Generate:

PRODUCTION_BENCHMARK_REPORT.md

Expected target:

API latency < 100ms
Prediction latency < 20ms
MC 1000 sims < 50ms
NON-GOALS

Do NOT implement:

Injury Engine
Weather Engine
Altitude Engine
New forecasting models
New frontend pages
New statistical methodologies

Those belong to future phases.

Focus exclusively on production hardening.

FINAL DELIVERABLES

Generate:

PRODUCTION_HARDENING_REPORT.md

containing:

Changes implemented
Security improvements
Observability improvements
Test results
Coverage results
Benchmark results
Remaining technical debt
Updated production readiness score

And finally answer:

Would you deploy this to production today?
YES / NO

Justify the answer technically.