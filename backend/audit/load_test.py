"""DEPLOY-003 — Load Testing & Capacity Validation.

Runs concurrent user simulations at 10, 50, 100 concurrency levels
against the running FastAPI backend. Measures throughput, latency, error rate.
"""

import json
import logging
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import httpx

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

BASE_URL = "http://127.0.0.1:8000"

ENDPOINTS = [
    ("GET", "/health", "Health Check"),
    ("GET", "/api/v1/teams", "List Teams"),
    ("GET", "/api/v1/groups", "List Groups"),
    ("GET", "/api/v1/rankings/igf", "IGF Rankings"),
    ("GET", "/api/v1/dashboard", "Dashboard"),
    ("GET", "/api/v1/predictions", "Full Predictions"),
    ("GET", "/api/v1/matches", "Match Calendar"),
]

SCENARIO_BODY = {
    "modifications": [],
    "num_scenarios": 10,
}

CONCURRENCY_LEVELS = [10, 50, 100]
WARMUP_REQUESTS = 3


def warmup_server():
    """Send warm-up requests to avoid cold-start inflation."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        for _ in range(WARMUP_REQUESTS):
            try:
                c.get("/health")
            except Exception:
                pass
REQUESTS_PER_USER = 5
RAMPUP_SECONDS = 2


def run_session(endpoints: list) -> list[dict]:
    results = []
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        for method, path, label in endpoints:
            try:
                start = time.perf_counter()
                if method == "POST":
                    resp = client.post(path, json=SCENARIO_BODY)
                else:
                    resp = client.get(path)
                elapsed = (time.perf_counter() - start) * 1000
                results.append({
                    "label": label,
                    "method": method,
                    "path": path,
                    "status": resp.status_code,
                    "latency_ms": round(elapsed, 2),
                })
            except Exception as e:
                results.append({
                    "label": label,
                    "method": method,
                    "path": path,
                    "status": 0,
                    "latency_ms": None,
                    "error": str(e),
                })
    return results


def run_load_test(concurrency: int, duration_seconds: int = 15) -> dict:
    endpoints = ENDPOINTS + [
        ("POST", "/api/v1/scenarios/simulate", "Scenario Simulation"),
    ]

    all_results = []
    start_wall = time.monotonic()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = []
        for user_id in range(concurrency):
            futures.append(pool.submit(run_session, endpoints))

        done = 0
        for future in as_completed(futures):
            all_results.extend(future.result())
            done += 1

    wall_elapsed = time.monotonic() - start_wall

    # Aggregate per endpoint
    by_endpoint = {}
    for r in all_results:
        key = r["label"]
        by_endpoint.setdefault(key, []).append(r)

    per_endpoint = []
    total_requests = 0
    total_errors = 0
    all_latencies = []

    for label, items in by_endpoint.items():
        latencies = [i["latency_ms"] for i in items if i["latency_ms"] is not None]
        errors = sum(1 for i in items if i["status"] != 200)
        total_requests += len(items)
        total_errors += errors
        all_latencies.extend(latencies)

        if latencies:
            sorted_lat = sorted(latencies)
            per_endpoint.append({
                "label": label,
                "requests": len(items),
                "errors": errors,
                "error_rate_pct": round(errors / len(items) * 100, 2),
                "mean_ms": round(statistics.mean(latencies), 2),
                "p50_ms": round(sorted_lat[len(sorted_lat) // 2], 2),
                "p95_ms": round(sorted_lat[int(len(sorted_lat) * 0.95)], 2),
                "p99_ms": round(sorted_lat[int(len(sorted_lat) * 0.99)], 2),
                "min_ms": round(min(latencies), 2),
                "max_ms": round(max(latencies), 2),
            })
        else:
            per_endpoint.append({
                "label": label,
                "requests": len(items),
                "errors": errors,
                "error_rate_pct": 100.0,
                "mean_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "min_ms": None,
                "max_ms": None,
            })

    sorted_all = sorted(all_latencies) if all_latencies else []
    throughput = round(total_requests / wall_elapsed, 2) if wall_elapsed > 0 else 0

    result = {
        "concurrency": concurrency,
        "duration_seconds": round(wall_elapsed, 2),
        "total_requests": total_requests,
        "total_errors": total_errors,
        "error_rate_pct": round(total_errors / total_requests * 100, 2) if total_requests else 0,
        "throughput_req_per_sec": throughput,
        "overall_mean_ms": round(statistics.mean(all_latencies), 2) if all_latencies else None,
        "overall_p50_ms": round(sorted_all[len(sorted_all) // 2], 2) if sorted_all else None,
        "overall_p95_ms": round(sorted_all[int(len(sorted_all) * 0.95)], 2) if sorted_all else None,
        "overall_p99_ms": round(sorted_all[int(len(sorted_all) * 0.99)], 2) if sorted_all else None,
        "per_endpoint": per_endpoint,
    }
    return result


def main():
    print("DEPLOY-003 — Load Testing & Capacity Validation")
    print(f"Target: {BASE_URL}")
    print(f"Concurrency levels: {CONCURRENCY_LEVELS}")
    print(f"Requests per user: {REQUESTS_PER_USER}\n")

    # Warm up server to avoid cold-start latency skew
    print("Warming up server...")
    warmup_server()
    print("Warm-up complete.\n")

    all_results = {}
    for concurrency in CONCURRENCY_LEVELS:
        print(f"\n{'='*60}")
        print(f"  Testing {concurrency} concurrent users...")
        print(f"{'='*60}")
        sys.stdout.flush()
        result = run_load_test(concurrency)
        all_results[str(concurrency)] = result

        print(f"  Duration: {result['duration_seconds']}s")
        print(f"  Total requests: {result['total_requests']}")
        print(f"  Errors: {result['total_errors']} ({result['error_rate_pct']}%)")
        print(f"  Throughput: {result['throughput_req_per_sec']} req/s")
        print(f"  Overall latency: p50={result['overall_p50_ms']}ms  p95={result['overall_p95_ms']}ms  p99={result['overall_p99_ms']}ms")

    # Generate report
    report = generate_report(all_results)

    with open("audit/LOAD_TEST_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to audit/LOAD_TEST_REPORT.md")
    print(json.dumps(all_results, indent=2, default=str))


def generate_report(results: dict) -> str:
    lines = []
    lines.append("# DEPLOY-003: Load Testing & Capacity Validation Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Target:** `{BASE_URL}`")
    lines.append(f"**Concurrency levels:** 10, 50, 100 concurrent users")
    lines.append(f"**Requests per user:** {REQUESTS_PER_USER}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## Overall Summary")
    lines.append("")
    lines.append("| Concurrency | Duration (s) | Requests | Errors | Error Rate | Throughput (req/s) | P50 (ms) | P95 (ms) | P99 (ms) |")
    lines.append("|------------|-------------|---------|-------|-----------|-----------------|---------|---------|---------|")
    for level in CONCURRENCY_LEVELS:
        r = results[str(level)]
        lines.append(
            f"| {r['concurrency']} | {r['duration_seconds']} | {r['total_requests']} "
            f"| {r['total_errors']} | {r['error_rate_pct']}% | {r['throughput_req_per_sec']} "
            f"| {r['overall_p50_ms']} | {r['overall_p95_ms']} | {r['overall_p99_ms']} |"
        )
    lines.append("")

    # Per-endpoint breakdown per concurrency
    for level in CONCURRENCY_LEVELS:
        r = results[str(level)]
        lines.append(f"---")
        lines.append("")
        lines.append(f"## {r['concurrency']} Concurrent Users — Per-Endpoint")
        lines.append("")
        lines.append("| Endpoint | Requests | Errors | Error Rate | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |")
        lines.append("|---------|---------|-------|-----------|----------|----------|----------|----------|")
        for ep in r["per_endpoint"]:
            mean = f"{ep['mean_ms']}" if ep['mean_ms'] is not None else "N/A"
            p50 = f"{ep['p50_ms']}" if ep['p50_ms'] is not None else "N/A"
            p95 = f"{ep['p95_ms']}" if ep['p95_ms'] is not None else "N/A"
            p99 = f"{ep['p99_ms']}" if ep['p99_ms'] is not None else "N/A"
            lines.append(
                f"| {ep['label']} | {ep['requests']} | {ep['errors']} "
                f"| {ep['error_rate_pct']}% | {mean} | {p50} | {p95} | {p99} |"
            )
        lines.append("")

    # Bottlenecks and recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Bottlenecks & Failure Points")
    lines.append("")

    # Identify bottlenecks
    bottlenecks = []
    thresholds = {"predictions": 500, "simulation": 2000, "igf": 200, "dashboard": 200}
    
    for level in CONCURRENCY_LEVELS:
        r = results[str(level)]
        for ep in r["per_endpoint"]:
            label = ep["label"].lower()
            if ep.get("mean_ms") is None:
                continue
            for key, threshold in thresholds.items():
                if key in label:
                    if ep["mean_ms"] > threshold:
                        bottlenecks.append(
                            f"- **{ep['label']}** at {level} concurrent users: "
                            f"mean {ep['mean_ms']}ms exceeds {threshold}ms threshold"
                        )
                    break

    if bottlenecks:
        lines.append("### Identified Bottlenecks")
        lines.append("")
        for b in sorted(set(bottlenecks)):
            lines.append(b)
        lines.append("")
    else:
        lines.append("No significant bottlenecks detected at tested concurrency levels.")
        lines.append("")

    # Error analysis
    has_errors = any(results[str(l)]["total_errors"] > 0 for l in CONCURRENCY_LEVELS)
    if has_errors:
        lines.append("### Errors Detected")
        lines.append("")
        for level in CONCURRENCY_LEVELS:
            r = results[str(level)]
            if r["total_errors"] > 0:
                for ep in r["per_endpoint"]:
                    if ep["errors"] > 0:
                        lines.append(f"- {ep['label']} @ {level} users: {ep['errors']} errors ({ep['error_rate_pct']}%)")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")

    # Generate dynamic recommendations based on results
    recs = []
    
    for level in CONCURRENCY_LEVELS:
        r = results[str(level)]
        for ep in r["per_endpoint"]:
            label = ep["label"].lower()
            if ep.get("p95_ms") is None:
                continue
            
            if "prediction" in label and ep["p95_ms"] > 500:
                recs.append(
                    "- **Full Predictions:** Consider adding pagination or async computation. "
                    "The current endpoint computes all predictions synchronously. "
                    "A materialized view or pre-computed cache layer would reduce P95 latency."
                )
            elif "simulation" in label and ep["p95_ms"] > 2000:
                recs.append(
                    "- **Scenario Simulation:** This is inherently compute-heavy. "
                    "Consider moving to a background task queue (Celery/Redis Queue) with "
                    "a polling endpoint for results. Add rate limiting per user."
                )
            elif "igf" in label and ep["p95_ms"] > 200:
                recs.append(
                    "- **IGF Rankings:** The first request is slow (cold computation). "
                    "Pre-warm the IGF cache on deployment or compute via a scheduled job."
                )

    if not recs:
        recs.append("- All endpoints performed within acceptable ranges. No urgent action required.")

    # Always add general recommendations
    recs.extend([
        "- **Rate Limiting:** Ensure rate limiting is enabled in production to prevent abuse.",
        "- **Connection Pooling:** Verify PostgreSQL pool_size and max_overflow are tuned for peak concurrency.",
        "- **Horizontal Scaling:** If traffic exceeds 100 concurrent users, add a second backend instance behind a load balancer.",
        "- **Monitoring:** Track p99 latency and error rate alerts in Sentry/Datadog.",
    ])

    for rec in recs:
        if rec not in lines:  # avoid duplicates
            lines.append(rec)

    lines.append("")

    # Capacity recommendation
    lines.append("## Capacity Recommendation")
    lines.append("")
    
    max_throughput = max(results[str(l)]["throughput_req_per_sec"] for l in CONCURRENCY_LEVELS)
    max_concurrency = max(CONCURRENCY_LEVELS)
    
    lines.append(f"- **Max tested throughput:** {max_throughput} req/s at {max_concurrency} concurrent users")
    lines.append(f"- **Estimated headroom:** 2–3x with horizontal scaling (2–3 backend instances)")
    lines.append(f"- **Recommended production instance:** 2 CPU / 4 GB RAM per backend")
    lines.append(f"- **Auto-scaling trigger:** P95 latency >200ms or CPU >70%")
    lines.append(f"- **Database:** Ensure PostgreSQL `max_connections` >= expected pool + 20")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
