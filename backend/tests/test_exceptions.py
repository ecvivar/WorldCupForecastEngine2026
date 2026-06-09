from app.core.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    CalibrationError,
    ExternalServiceError,
    NotFoundError,
    SimulationError,
    ValidationError,
)


class TestAppError:
    def test_base_error_defaults(self):
        err = AppError()
        assert err.status_code == 500
        assert err.code == "INTERNAL_ERROR"
        assert err.message == "Internal error"

    def test_base_error_with_message(self):
        err = AppError("custom message", request_id="req-123")
        assert err.message == "custom message"
        assert err.request_id == "req-123"

    def test_to_dict(self):
        err = AppError("test error", request_id="req-456")
        d = err.to_dict()
        assert d["success"] is False
        assert d["error"]["code"] == "INTERNAL_ERROR"
        assert d["error"]["message"] == "test error"
        assert d["error"]["request_id"] == "req-456"

    def test_validation_error(self):
        err = ValidationError("invalid input")
        assert err.status_code == 400
        assert err.code == "VALIDATION_ERROR"

    def test_authentication_error(self):
        err = AuthenticationError("unauthorized")
        assert err.status_code == 401
        assert err.code == "AUTHENTICATION_ERROR"

    def test_authorization_error(self):
        err = AuthorizationError("forbidden")
        assert err.status_code == 403
        assert err.code == "AUTHORIZATION_ERROR"

    def test_not_found_error(self):
        err = NotFoundError("not found")
        assert err.status_code == 404
        assert err.code == "NOT_FOUND"

    def test_simulation_error(self):
        err = SimulationError("sim failed")
        assert err.status_code == 500
        assert err.code == "SIMULATION_ERROR"

    def test_calibration_error(self):
        err = CalibrationError("cal failed")
        assert err.status_code == 500
        assert err.code == "CALIBRATION_ERROR"

    def test_external_service_error(self):
        err = ExternalServiceError("external failed")
        assert err.status_code == 502
        assert err.code == "EXTERNAL_SERVICE_ERROR"
