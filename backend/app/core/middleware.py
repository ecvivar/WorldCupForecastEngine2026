import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.metrics import inc_active_requests, dec_active_requests, inc_request_count, record_request_duration


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        cs_policy = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;"
        if request.url.path in ("/docs", "/redoc"):
            cs_policy = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:;"
        response.headers["Content-Security-Policy"] = cs_policy
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        inc_active_requests()
        inc_request_count(request.url.path)
        start = time.time()
        try:
            response = await call_next(request)
            return response
        finally:
            duration = (time.time() - start) * 1000
            record_request_duration(request.url.path, duration)
            dec_active_requests()
