from app.core.metrics import (
    compute_avg,
    dec_active_requests,
    get_metrics,
    get_prometheus_text,
    inc_active_requests,
    inc_request_count,
    record_cache_hit,
    record_cache_miss,
    record_db_query_duration,
    record_request_duration,
    record_simulation_duration,
    request_count,
)


class TestMetrics:
    def setup_method(self):
        request_count.clear()

    def test_request_count(self):
        inc_request_count("/api/v1/teams")
        inc_request_count("/api/v1/teams")
        inc_request_count("/api/v1/rankings")
        metrics = get_metrics()
        assert metrics["http"]["total_requests"] == 3
        assert metrics["http"]["by_endpoint"]["/api/v1/teams"] == 2

    def test_active_requests(self):
        inc_active_requests()
        inc_active_requests()
        metrics = get_metrics()
        assert metrics["http"]["active_requests"] == 2
        dec_active_requests()
        metrics = get_metrics()
        assert metrics["http"]["active_requests"] == 1

    def test_request_duration(self):
        record_request_duration("/test", 100.0)
        record_request_duration("/test", 200.0)
        metrics = get_metrics()
        assert metrics["http"]["avg_duration_ms"] >= 150.0

    def test_cache_hits(self):
        record_cache_hit()
        record_cache_hit()
        record_cache_miss()
        metrics = get_metrics()
        assert metrics["cache"]["hits"] >= 2
        assert metrics["cache"]["misses"] >= 1

    def test_cache_hit_rate(self):
        metrics = get_metrics()
        assert metrics["cache"]["hit_rate_pct"] >= 0

    def test_simulation_duration(self):
        record_simulation_duration(5000.0)
        record_simulation_duration(15000.0)
        metrics = get_metrics()
        assert metrics["simulations"]["count"] >= 2
        assert metrics["simulations"]["avg_duration_ms"] is not None

    def test_db_query_duration(self):
        record_db_query_duration(50.0)
        record_db_query_duration(150.0)
        metrics = get_metrics()
        assert metrics["database"]["query_count"] >= 2
        assert metrics["database"]["avg_query_duration_ms"] is not None

    def test_prometheus_text_format(self):
        text = get_prometheus_text()
        assert "# HELP http_requests_total" in text
        assert "# TYPE http_requests_total counter" in text
        assert "cache_hits_total" in text
        assert "cache_misses_total" in text
        assert "http_active_requests" in text
        assert "simulation_duration_ms" in text

    def test_compute_avg_empty(self):
        assert compute_avg([]) == 0.0

    def test_compute_avg_values(self):
        assert compute_avg([100, 200, 300]) == 200.0
