import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.metrics import get_prometheus_text
from app.db.session import SessionLocal

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "project": settings.project_name,
        "version": settings.project_version,
        "timestamp": time.time(),
    }


@router.get("/health/database")
def health_database():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


@router.get("/health/redis")
def health_redis():
    try:
        ok = get_cache().ping()
        if ok:
            return {"status": "ok", "redis": "connected"}
        return {"status": "error", "redis": "ping failed"}
    except Exception as e:
        return {"status": "error", "redis": str(e)}


@router.get("/health/system")
def health_system():
    return {
        "status": "ok",
        "python_version": __import__("platform").python_version(),
        "platform": __import__("platform").platform(),
        "cpu_count": __import__("os").cpu_count(),
    }


@router.get("/metrics")
def metrics():
    return get_prometheus_text()
