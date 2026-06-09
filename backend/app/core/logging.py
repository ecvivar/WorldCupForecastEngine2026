import json
import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("api")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        ts += f".{int(record.msecs):03d}Z"
        log_entry: dict = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        if record.exc_info:
            if isinstance(record.exc_info, bool):
                import sys
                record.exc_info = sys.exc_info()
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setFormatter(JSONFormatter())


class RequestLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.time()

        response = await call_next(request)

        duration = time.time() - start
        extra = {
            "request_id": request_id,
            "endpoint": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_agent": request.headers.get("user-agent", ""),
            "ip": request.client.host if request.client else "",
        }
        logger.info("HTTP %s %s -> %d (%.2fms)", request.method, request.url.path, response.status_code, duration * 1000, extra={"extra_fields": extra})
        return response


def log_simulation(simulation_id: str, teams: int, iterations: int, duration: float, success: bool) -> None:
    extra = {
        "simulation_id": simulation_id,
        "teams": teams,
        "iterations": iterations,
        "duration_ms": round(duration * 1000, 2),
        "success": success,
    }
    if success:
        logger.info("Simulation completed", extra={"extra_fields": extra})
    else:
        logger.error("Simulation failed", extra={"extra_fields": extra})


def log_calibration(dataset: str, metrics: dict, duration: float) -> None:
    extra = {
        "dataset": dataset,
        "metrics": metrics,
        "duration_ms": round(duration * 1000, 2),
    }
    logger.info("Calibration completed", extra={"extra_fields": extra})


def log_error(request_id: str, endpoint: str, stack_trace: str) -> None:
    extra = {
        "request_id": request_id,
        "endpoint": endpoint,
        "stack_trace": stack_trace,
    }
    logger.error("Unhandled error", extra={"extra_fields": extra})
