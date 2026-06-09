import logging
from dataclasses import dataclass, field

from sqlalchemy import text

from app.core.cache import get_cache
from app.core.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger("startup")


@dataclass
class StartupReadinessReport:
    database: bool = False
    redis: bool = False
    env_vars_valid: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.database and self.env_vars_valid


def check_startup_readiness() -> StartupReadinessReport:
    report = StartupReadinessReport()

    # Database
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        report.database = True
    except Exception as e:
        report.errors.append(f"Database connection failed: {e}")

    # Redis (optional — warn only)
    try:
        ok = get_cache().ping()
        if ok:
            report.redis = True
        else:
            logger.warning("Redis ping failed — caching disabled")
    except Exception:
        logger.warning("Redis not available — caching disabled")

    # Env vars
    settings = get_settings()
    if settings.secret_key == "change-me-in-production":
        report.errors.append("SECRET_KEY is still set to default value")
    else:
        report.env_vars_valid = True

    return report
