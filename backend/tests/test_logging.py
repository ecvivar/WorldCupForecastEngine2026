import json
import logging

from app.core.logging import JSONFormatter, log_calibration, log_error, log_simulation


class TestJSONFormatter:
    def test_basic_format(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "hello world"
        assert parsed["logger"] == "test"
        assert "timestamp" in parsed

    def test_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=42,
            msg="with extra", args=(), exc_info=None,
        )
        record.request_id = "req-abc-123"
        record.extra_fields = {"endpoint": "/health", "duration_ms": 42.5}
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["request_id"] == "req-abc-123"
        assert parsed["endpoint"] == "/health"
        assert parsed["duration_ms"] == 42.5

    def test_exception_format(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname=__file__, lineno=42,
                msg="error occurred", args=(), exc_info=True,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert "exception" in parsed
            assert "ValueError" in parsed["exception"]


class TestLogHelpers:
    def test_log_simulation_success(self, caplog):
        caplog.set_level(logging.INFO)
        log_simulation("sim-1", 48, 100000, 12.5, True)
        found = any(
            "Simulation completed" in rec.getMessage() for rec in caplog.records
        )
        assert found, "Should log simulation completion"

    def test_log_simulation_failure(self, caplog):
        caplog.set_level(logging.ERROR)
        log_simulation("sim-2", 48, 50000, 30.0, False)
        found = any(
            "Simulation failed" in rec.getMessage() for rec in caplog.records
        )
        assert found, "Should log simulation failure"

    def test_log_calibration(self, caplog):
        caplog.set_level(logging.INFO)
        log_calibration("2014-2022", {"accuracy": 0.85, "brier": 0.12}, 45.0)
        found = any(
            "Calibration completed" in rec.getMessage() for rec in caplog.records
        )
        assert found

    def test_log_error(self, caplog):
        caplog.set_level(logging.ERROR)
        log_error("req-999", "/api/v1/simulations/run", "Traceback ... ValueError")
        found = any(
            "Unhandled error" in rec.getMessage() for rec in caplog.records
        )
        assert found
