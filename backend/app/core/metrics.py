import time
from collections import defaultdict
from threading import Lock

_lock = Lock()

request_count: dict[str, int] = defaultdict(int)
request_duration: dict[str, list[float]] = defaultdict(list)
active_requests: int = 0
cache_hits_total: int = 0
cache_misses_total: int = 0
simulation_durations: list[float] = []
db_query_durations: list[float] = []
predictions_total: int = 0
simulations_total: int = 0
scenarios_total: int = 0
calibrations_total: int = 0


def inc_request_count(endpoint: str) -> None:
    with _lock:
        request_count[endpoint] += 1


def record_request_duration(endpoint: str, duration: float) -> None:
    with _lock:
        request_duration[endpoint].append(duration)
        if len(request_duration[endpoint]) > 1000:
            request_duration[endpoint] = request_duration[endpoint][-500:]


def inc_active_requests() -> None:
    global active_requests
    with _lock:
        active_requests += 1


def dec_active_requests() -> None:
    global active_requests
    with _lock:
        active_requests = max(0, active_requests - 1)


def record_cache_hit() -> None:
    global cache_hits_total
    with _lock:
        cache_hits_total += 1


def record_cache_miss() -> None:
    global cache_misses_total
    with _lock:
        cache_misses_total += 1


def record_simulation_duration(duration: float) -> None:
    global simulation_durations
    with _lock:
        simulation_durations.append(duration)
        if len(simulation_durations) > 100:
            simulation_durations = simulation_durations[-50:]


def inc_predictions_total() -> None:
    global predictions_total
    with _lock:
        predictions_total += 1


def inc_simulations_total() -> None:
    global simulations_total
    with _lock:
        simulations_total += 1


def inc_scenarios_total() -> None:
    global scenarios_total
    with _lock:
        scenarios_total += 1


def inc_calibrations_total() -> None:
    global calibrations_total
    with _lock:
        calibrations_total += 1


def record_db_query_duration(duration: float) -> None:
    global db_query_durations
    with _lock:
        db_query_durations.append(duration)
        if len(db_query_durations) > 1000:
            db_query_durations = db_query_durations[-500:]


def compute_avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def get_metrics() -> dict:
    with _lock:
        total_reqs = sum(request_count.values())
        avg_duration = compute_avg([d for durations in request_duration.values() for d in durations])
        hit_rate = 0.0
        total_cache = cache_hits_total + cache_misses_total
        if total_cache > 0:
            hit_rate = round(cache_hits_total / total_cache * 100, 1)
        avg_sim_duration = compute_avg(simulation_durations)
        avg_db_duration = compute_avg(db_query_durations)

    return {
        "http": {
            "total_requests": total_reqs,
            "active_requests": active_requests,
            "avg_duration_ms": avg_duration,
            "by_endpoint": dict(request_count),
        },
        "cache": {
            "hits": cache_hits_total,
            "misses": cache_misses_total,
            "hit_rate_pct": hit_rate,
        },
        "simulations": {
            "count": len(simulation_durations),
            "avg_duration_ms": avg_sim_duration,
        },
        "database": {
            "avg_query_duration_ms": avg_db_duration,
            "query_count": len(db_query_durations),
        },
        "operations": {
            "predictions_total": predictions_total,
            "simulations_total": simulations_total,
            "scenarios_total": scenarios_total,
            "calibrations_total": calibrations_total,
        },
    }


def get_prometheus_text() -> str:
    m = get_metrics()
    lines: list[str] = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
    ]
    for ep, count in m["http"]["by_endpoint"].items():
        safe = ep.replace("/", "_").replace("{", "_").replace("}", "_")
        lines.append(f'http_requests_total{{endpoint="{safe}"}} {count}')

    lines += [
        "",
        "# HELP http_active_requests Active requests",
        "# TYPE http_active_requests gauge",
        f"http_active_requests {m['http']['active_requests']}",
        "",
        "# HELP http_avg_duration_ms Average request duration",
        "# TYPE http_avg_duration_ms gauge",
        f"http_avg_duration_ms {m['http']['avg_duration_ms']}",
        "",
        "# HELP cache_hits_total Cache hits",
        "# TYPE cache_hits_total counter",
        f"cache_hits_total {m['cache']['hits']}",
        "",
        "# HELP cache_misses_total Cache misses",
        "# TYPE cache_misses_total counter",
        f"cache_misses_total {m['cache']['misses']}",
        "",
        "# HELP cache_hit_rate_pct Cache hit rate",
        "# TYPE cache_hit_rate_pct gauge",
        f"cache_hit_rate_pct {m['cache']['hit_rate_pct']}",
        "",
        "# HELP simulation_duration_ms Simulation duration",
        "# TYPE simulation_duration_ms gauge",
        f"simulation_duration_ms {m['simulations']['avg_duration_ms']}",
        "",
        "# HELP db_query_duration_ms Database query duration",
        "# TYPE db_query_duration_ms gauge",
        f"db_query_duration_ms {m['database']['avg_query_duration_ms']}",
        "",
        "# HELP predictions_total Total predictions computed",
        "# TYPE predictions_total counter",
        f"predictions_total {m['operations']['predictions_total']}",
        "",
        "# HELP simulations_total Total simulations run",
        "# TYPE simulations_total counter",
        f"simulations_total {m['operations']['simulations_total']}",
        "",
        "# HELP scenarios_total Total scenarios evaluated",
        "# TYPE scenarios_total counter",
        f"scenarios_total {m['operations']['scenarios_total']}",
        "",
        "# HELP calibrations_total Total calibrations performed",
        "# TYPE calibrations_total counter",
        f"calibrations_total {m['operations']['calibrations_total']}",
    ]
    return "\n".join(lines) + "\n"
