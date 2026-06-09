class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "Internal error", request_id: str | None = None):
        self.message = message
        self.request_id = request_id
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
            },
        }


class ValidationError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    status_code = 403
    code = "AUTHORIZATION_ERROR"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class SimulationError(AppError):
    status_code = 500
    code = "SIMULATION_ERROR"


class CalibrationError(AppError):
    status_code = 500
    code = "CALIBRATION_ERROR"


class ExternalServiceError(AppError):
    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
