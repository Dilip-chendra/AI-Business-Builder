"""Global exception handlers for FastAPI."""
import logging
from decimal import Decimal

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _safe_errors(errors: list) -> list:
    """Sanitize Pydantic v2 error dicts so they are always JSON-serialisable.

    Pydantic v2 can embed non-serialisable types (e.g. ``Decimal``) inside the
    ``ctx`` dict of a validation error.  We convert them to strings here.
    """
    safe = []
    for err in errors:
        sanitized = {}
        for k, v in err.items():
            if k == "ctx" and isinstance(v, dict):
                sanitized[k] = {ck: str(cv) if isinstance(cv, Decimal) else cv for ck, cv in v.items()}
            else:
                sanitized[k] = v
        safe.append(sanitized)
    return safe


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "HTTP %s on %s – %s  request_id=%s",
        exc.status_code,
        request.url.path,
        exc.detail,
        request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "Validation error on %s  request_id=%s  errors=%s",
        request.url.path,
        request_id,
        exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": _safe_errors(exc.errors()),
            "request_id": request_id,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception on %s  request_id=%s",
        request.url.path,
        request_id,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "request_id": request_id},
    )
