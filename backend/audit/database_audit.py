"""DEPLOY-004 — Database Validation Audit.

Measures SQL query count, duration, and detects N+1 patterns
for every API endpoint against the running PostgreSQL database.
"""

import json
import logging
import os
import sys
import time
import uuid

sys.path.insert(0, ".")

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5433/worldcup_forecast"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CACHE_ENABLED"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["SECRET_KEY"] = "audit-secret-key-32-chars!!"

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from app.models import (  # noqa: F401
    competition, elo_rating, fifa_ranking, group,
    group_standing, match, player, simulation, team, xg_metrics,
)
from app.db.session import Base, engine as app_engine
from app.core.dependencies import get_db
from app.main import app

_test_engine = create_engine(
    "postgresql+psycopg://postgres:postgres@localhost:5433/worldcup_forecast",
    pool_size=5, max_overflow=10,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
Base.metadata.create_all(bind=_test_engine)

def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = _override_get_db

ENDPOINTS = [
    ("GET", "/health", "Health Check"),
    ("GET", "/api/v1/teams", "List Teams"),
    ("GET", "/api/v1/groups", "List Groups"),
    ("GET", "/api/v1/rankings/igf", "IGF Rankings"),
    ("GET", "/api/v1/dashboard", "Dashboard"),
    ("GET", "/api/v1/predictions", "Full Predictions"),
    ("GET", "/api/v1/matches", "Match Calendar"),
    ("POST", "/api/v1/scenarios/simulate", "Scenario Simulation"),
]

SCENARIO_BODY = {"modifications": [], "num_scenarios": 10}

query_log = []

def before_execute(conn, clause, multiparams, params, execution_options):
    query_log.append({
        "start": time.perf_counter(),
        "statement": str(clause.compile(compile_kwargs={"literal_binds": True})),
        "params": str(params),
    })

def after_execute(conn, clause, multiparams, params, result, execution_options):
    if query_log:
        query_log[-1]["duration_ms"] = round((time.perf_counter() - query_log[-1]["start"]) * 1000, 2)

event.listen(_test_engine, "before_execute", before_execute)
event.listen(_test_engine, "after_execute", after_execute)

def audit_endpoints() -> list[dict]:
    results = []
    endpoint_results = []

    with TestClient(app) as client:
        for method, path, label in ENDPOINTS:
            query_log.clear()

            try:
                if method == "POST":
                    resp = client.post(path, json=SCENARIO_BODY)
                else:
                    resp = client.get(path)
                status = resp.status_code
                body_approx_len = len(resp.text) if resp.text else 0
            except Exception as e:
                status = 0
                body_approx_len = 0

            queries = list(query_log)
            total_queries = len(queries)
            total_duration = round(sum(q.get("duration_ms", 0) for q in queries), 2)
            slow_queries = [q for q in queries if q.get("duration_ms", 0) > 50]

            all_statements = [q["statement"] for q in queries]

            n_plus_1 = detect_n_plus_1(all_statements)

            ep = {
                "endpoint": label,
                "method": method,
                "path": path,
                "status": status,
                "query_count": total_queries,
                "total_duration_ms": total_duration,
                "slow_queries": len(slow_queries),
                "slow_query_details": [
                    {"sql": q["statement"][:200], "duration_ms": q["duration_ms"]}
                    for q in slow_queries[:5]
                ],
                "n_plus_1_detected": n_plus_1["detected"],
                "n_plus_1_detail": n_plus_1["detail"],
                "response_size_bytes": body_approx_len,
            }
            endpoint_results.append(ep)

    return endpoint_results


def detect_n_plus_1(statements: list[str]) -> dict:
    """Heuristic: same table SELECT inside a loop = N+1 pattern."""
    counts = {}
    for s in statements:
        lower = s.lower().strip()
        for keyword in ["from ", "join "]:
            if keyword in lower:
                parts = lower.split(keyword)
                for p in parts[1:]:
                    table = p.strip().split()[0].strip('"').strip("'")
                    if table and table not in ("(", "select", "where", "and", "or"):
                        counts[table] = counts.get(table, 0) + 1

    patterns = []
    for table, count in counts.items():
        if count >= 3 and sum(1 for s in statements if table.lower() in s.lower()) >= 3:
            patterns.append(f"{table} queried {count} times")

    return {
        "detected": len(patterns) > 0,
        "detail": "; ".join(patterns) if patterns else "No repetitive query pattern detected",
    }


def check_missing_indexes() -> list[str]:
    """Check for common missing-index patterns."""
    findings = []

    check_queries = [
        (
            "FK on match predictions",
            """
            SELECT COUNT(*) FROM (
                SELECT m.id, p.team_id
                FROM matches m
                LEFT JOIN predictions p ON m.id = p.match_id
                WHERE p.id IS NULL
            ) sub
            """,
        ),
    ]

    try:
        db = TestingSessionLocal()

        # Query stats
        rows = db.execute(text("""
            SELECT schemaname,relname,seq_scan,seq_tup_read,idx_scan,idx_tup_fetch
            FROM pg_stat_user_tables
            ORDER BY seq_tup_read DESC
            LIMIT 15
        """)).fetchall()
        for row in rows:
            if row.seq_scan > 0 and row.seq_tup_read > 1000:
                findings.append(
                f"Table '{row.relname}': {row.seq_scan} seq scans reading "
                f"{row.seq_tup_read} tuples (idx_scan={row.idx_scan})"
            )

        # Missing indexes on FK columns
        rows = db.execute(text("""
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
                AND NOT EXISTS (
                    SELECT 1 FROM pg_indexes pi
                    WHERE pi.tablename = tc.table_name
                    AND pi.indexdef LIKE '%' || kcu.column_name || '%'
                )
            ORDER BY tc.table_name, kcu.column_name
        """)).fetchall()
        for row in rows:
            findings.append(
                f"Missing index: {row.table_name}.{row.column_name} "
                f"(FK to {row.foreign_table_name})"
            )

        db.close()
    except Exception as e:
        findings.append(f"Error checking indexes: {e}")

    return findings


def check_table_sizes(db_url: str) -> list[str]:
    details = []
    try:
        engine = create_engine(db_url, pool_size=2, max_overflow=2)
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT relname AS table,
                       n_live_tup AS row_estimate,
                       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
            """)).fetchall()
            for row in rows:
                details.append(f"  {row.table}: ~{row.row_estimate} rows, {row.total_size}")
        engine.dispose()
    except Exception as e:
        details.append(f"  Error: {e}")
    return details


def main():
    print("DEPLOY-004 — Database Validation Audit")
    print(f"Database: PostgreSQL 16 on localhost:5433")

    print("\n--- Table Sizes ---")
    for line in check_table_sizes(
        "postgresql+psycopg://postgres:postgres@localhost:5433/worldcup_forecast"
    ):
        print(line)

    print("\n--- Missing Index Check ---")
    missing = check_missing_indexes()
    if missing:
        for f in missing:
            print(f"  {f}")
    else:
        print("  No issues found.")

    print("\n--- Endpoint Query Audit ---")
    results = audit_endpoints()
    for ep in results:
        n1 = "N+1" if ep["n_plus_1_detected"] else "OK"
        print(f"  {ep['endpoint']:20s} | queries={ep['query_count']:2d} | "
              f"time={ep['total_duration_ms']:7.1f}ms | slow={ep['slow_queries']:2d} | "
              f"{n1:5s} | status={ep['status']}")

    # Generate report
    report = generate_report(results, missing)

    with open("audit/DATABASE_AUDIT_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to audit/DATABASE_AUDIT_REPORT.md")


def generate_report(endpoint_results: list[dict], index_issues: list[str]) -> str:
    lines = []
    lines.append("# DEPLOY-004: Database Validation Audit Report")
    lines.append("")
    lines.append("**Database:** PostgreSQL 16.14 on localhost:5433")
    lines.append("**Pool:** `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Table Sizes & Scan Statistics")
    lines.append("")
    lines.append("| Table | Estimated Rows | Total Size | Seq Scans | Tuples Read by Seq Scan |")
    lines.append("|-------|---------------|-----------|----------|------------------------|")
    try:
        db = TestingSessionLocal()
        rows = db.execute(text("""
            SELECT relname, n_live_tup,
                   pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
                   seq_scan, seq_tup_read
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
        """)).fetchall()
        for r in rows:
            lines.append(f"| {r.relname} | ~{r.n_live_tup} | {r.total_size} | {r.seq_scan} | {r.seq_tup_read} |")
        db.close()
    except Exception:
        lines.append("| _query failed_ | — | — | — | — |")
    lines.append("")

    lines.append("## Missing Indexes")
    lines.append("")
    if index_issues:
        for f in index_issues:
            lines.append(f"- {f}")
    else:
        lines.append("No missing indexes detected on foreign keys.")
    lines.append("")

    lines.append("## Endpoint Query Profile")
    lines.append("")
    lines.append("| Endpoint | Method | Queries | Total Time (ms) | Slow (>50ms) | N+1? | Status |")
    lines.append("|---------|--------|-------|---------------|-------------|------|--------|")
    for ep in endpoint_results:
        n1 = "YES" if ep["n_plus_1_detected"] else "no"
        lines.append(
            f"| {ep['endpoint']} | {ep['method']} | {ep['query_count']} | "
            f"{ep['total_duration_ms']} | {ep['slow_queries']} | {n1} | {ep['status']} |"
        )
    lines.append("")

    for ep in endpoint_results:
        lines.append(f"### {ep['endpoint']} (`{ep['method']} {ep['path']}`)")
        lines.append("")
        lines.append(f"- **Query count:** {ep['query_count']}")
        lines.append(f"- **Total query time:** {ep['total_duration_ms']}ms")
        lines.append(f"- **Slow queries (>50ms):** {ep['slow_queries']}")
        lines.append(f"- **N+1 detected:** {'Yes' if ep['n_plus_1_detected'] else 'No'}")

        if ep["n_plus_1_detected"]:
            lines.append(f"- **N+1 detail:** {ep['n_plus_1_detail']}")

        if ep["slow_queries"] > 0:
            lines.append("- **Slow query details:**")
            for sq in ep["slow_query_details"]:
                lines.append(f"  - `{sq['sql']}` ({sq['duration_ms']}ms)")

        lines.append("")

    lines.append("## N+1 Query Analysis")
    lines.append("")
    n1_endpoints = [ep for ep in endpoint_results if ep["n_plus_1_detected"]]
    if n1_endpoints:
        for ep in n1_endpoints:
            lines.append(f"- **{ep['endpoint']}**: {ep['n_plus_1_detail']}")
    else:
        lines.append("No N+1 query patterns detected across all endpoints.")
    lines.append("")

    lines.append("## Connection Pooling")
    lines.append("")
    lines.append("| Parameter | Current | Recommendation |")
    lines.append("|----------|---------|---------------|")
    lines.append("| `pool_size` | 10 | 20 for production (2× worker count) |")
    lines.append("| `max_overflow` | 20 | 20 (keeps burst capacity) |")
    lines.append("| `pool_pre_ping` | True | ✅ Good — prevents stale connections |")
    lines.append("| `pool_recycle` | not set | Add 3600s for production |")
    lines.append("| `max_connections` (DB) | 100 (default) | 200 for production |")
    lines.append("")

    lines.append("## Transaction Handling")
    lines.append("")
    lines.append("- **Scope:** Each request opens one session (via `get_db` dependency),")
    lines.append("  commits on success, rolls back on error.")
    lines.append("- **Auto-flush:** `False` — explicit flush required.")
    lines.append("- **Auto-commit:** `False` — explicit commit required.")
    lines.append("- **Assessment:** Correct for read-heavy workloads. OK.")
    lines.append("")

    lines.append("## Optimization Opportunities")
    lines.append("")

    optimization_found = False

    if any(ep["n_plus_1_detected"] for ep in endpoint_results):
        optimization_found = True
        lines.append("### High Priority")
        lines.append("")
        lines.append("1. **Fix N+1 queries** — Use `joinedload()` or `selectinload()` in the")
        lines.append("   following endpoints to eager-load relationships:")
        for ep in endpoint_results:
            if ep["n_plus_1_detected"]:
                lines.append(f"   - `{ep['endpoint']}`: {ep['n_plus_1_detail']}")
        lines.append("")

    high_query = [ep for ep in endpoint_results if ep["query_count"] > 5 and ep["slow_queries"] > 0]
    if high_query:
        if not optimization_found:
            lines.append("### High Priority")
            lines.append("")
            optimization_found = True

        lines.append("### Medium Priority")
        lines.append("")
        for ep in high_query:
            lines.append(f"- **{ep['endpoint']}** ({ep['query_count']} queries, "
                         f"{ep['total_duration_ms']}ms): Review query plan — "
                         f"consider adding composite indexes or materialized views.")

    if not optimization_found:
        lines.append("No immediate optimization opportunities identified.")
        lines.append("")

    lines.append("### General Recommendations")
    lines.append("")
    lines.append("1. **Add composite indexes** for common query patterns:")
    lines.append("   - `(team_id, rating_date)` on `elo_ratings`, `fifa_rankings`, `xg_metrics`")
    lines.append("     (covers 'latest for team' queries)")
    lines.append("   - `(competition_id, stage)` on `matches`")
    lines.append("     (covers match filtering by competition + stage)")
    lines.append("   - `(competition_id, name)` on `groups`")
    lines.append("     (covers group lookup within a competition)")
    lines.append("2. **Add `pool_recycle=3600`** to prevent PostgreSQL from dropping")
    lines.append("   idle connections after the default `tcp_keepalives_idle` timeout.")
    lines.append("3. **Set `statement_timeout=30000`** on the production engine to")
    lines.append("   kill runaway queries after 30 seconds.")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
