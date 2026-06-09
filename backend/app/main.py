from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import (
    analysis,
    calibration,
    calibration_refinement,
    comparison,
    dashboard,
    export,
    groups,
    health,
    matches,
    predictions,
    rankings,
    scenarios,
    simulations,
    teams,
)
from app.core.config import get_settings
from app.core.error_handler import (
    app_error_handler,
    http_exception_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.exceptions import AppError
from app.core.logging import RequestLogMiddleware, setup_logging
from app.core.middleware import MetricsMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.core.startup import check_startup_readiness
from app.db.session import engine, Base

settings = get_settings()
setup_logging()

# --- Sentry ---
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=0.1,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.models import (  # noqa: F401
        competition,
        elo_rating,
        fifa_ranking,
        group,
        group_standing,
        match,
        player,
        simulation,
        team,
        xg_metrics,
    )
    Base.metadata.create_all(bind=engine)
    report = check_startup_readiness()
    if report.errors:
        import logging
        logger = logging.getLogger("startup")
        for err in report.errors:
            logger.error("Startup issue: %s", err)
    yield


app = FastAPI(
    title=settings.project_name,
    version=settings.project_version,
    description="Professional World Cup 2026 Tournament Forecasting Engine — "
    "simulate match outcomes, group stages, and entire tournaments with Monte Carlo methods.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS (explicit origins) ---
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# --- Middleware stack (order: bottom-up, outer=last added) ---
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestLogMiddleware)

# --- Error handlers ---
from fastapi import HTTPException
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

# --- Routers ---
app.include_router(health.router)
app.include_router(teams.router, prefix=settings.api_prefix)
app.include_router(matches.router, prefix=settings.api_prefix)
app.include_router(groups.router, prefix=settings.api_prefix)
app.include_router(predictions.router, prefix=settings.api_prefix)
app.include_router(rankings.router, prefix=settings.api_prefix)
app.include_router(simulations.router, prefix=settings.api_prefix)
app.include_router(calibration.router, prefix=settings.api_prefix)
app.include_router(analysis.router, prefix=settings.api_prefix)
app.include_router(calibration_refinement.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
app.include_router(comparison.router, prefix=settings.api_prefix)
app.include_router(export.router, prefix=settings.api_prefix)
app.include_router(scenarios.router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
