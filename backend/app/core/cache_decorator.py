import functools
import inspect
import logging

from fastapi.encoders import jsonable_encoder

from app.core.cache import get_cache

logger = logging.getLogger("cache")


def cached(key_prefix: str, ttl: int | None = None):
    """
    Decorator to cache FastAPI endpoint responses using Cache Aside pattern.

    The cache key is: {key_prefix}:{args_kwargs_hash}
    If the function already returns a cached dict (from get_sync), it's returned directly.
    Otherwise, the function is executed, the result is stored in cache, and returned.

    Usage:
        @router.get("/rankings/igf")
        @cached("rankings:igf")
        def get_igf_rankings(db: Session = Depends(get_db)):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build a deterministic cache key from the function name + call signature
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Exclude db session from key (not hashable)
            call_parts = []
            for param_name, param_value in bound.arguments.items():
                if param_name in ("db", "session", "request"):
                    continue
                call_parts.append(f"{param_name}={param_value}")

            call_str = "|".join(call_parts)
            cache_key = f"{key_prefix}:{call_str}"

            cache = get_cache()
            cached_val = cache.get_sync(cache_key)
            if cached_val is not None:
                return cached_val

            result = func(*args, **kwargs)
            cache.set_sync(cache_key, jsonable_encoder(result))
            return result

        return wrapper

    return decorator
