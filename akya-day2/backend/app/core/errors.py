"""Typed application errors and the single handler that maps them to JSON."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class SentinelError(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    error: str = "internal_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(SentinelError):
    status_code = 404
    error = "not_found"


class DataUnavailableError(SentinelError):
    """Organizer data files are missing or unreadable."""

    status_code = 503
    error = "data_unavailable"


class DetectorError(SentinelError):
    status_code = 502
    error = "detector_error"


class LLMError(SentinelError):
    status_code = 502
    error = "llm_error"


class TuningValidationError(SentinelError):
    """Admin tuning breaks a rule; detail is "<path>: <code> [arg]" joined with "; "."""

    status_code = 422
    error = "invalid_tuning"


class TuningStoreError(SentinelError):
    """The admin override file could not be written."""

    status_code = 503
    error = "tuning_store_error"


def register_exception_handlers(app: FastAPI) -> None:
    """Map `SentinelError` subclasses to `{error, detail}` JSON responses."""

    @app.exception_handler(SentinelError)
    async def _handle(_: Request, exc: SentinelError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"error": exc.error, "detail": exc.detail}
        )
