from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.shared.exceptions.error_code import AppException, ErrorCode


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle AppException and return a structured error response."""
    logger.warning(
        "AppException | code={} msg={} path={}",
        exc.code.value,
        exc.message,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code.value,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle Pydantic / FastAPI validation errors (422)."""
    from fastapi.exceptions import RequestValidationError

    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        logger.warning(
            "ValidationError | path={} errors={}",
            request.url.path,
            errors,
        )
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.UNPROCESSABLE_ENTITY.value,
                "message": "Validation error",
                "detail": {"errors": errors},
            },
        )
    return await unhandled_exception_handler(request, exc)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all for unexpected errors."""
    logger.error(
        "UnhandledException | path={} exc_type={} exc={}",
        request.url.path,
        type(exc).__name__,
        str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.INTERNAL_ERROR.value,
            "message": "Internal server error",
            "detail": {},
        },
    )


def register_exception_handlers(app: "FastAPI") -> None:  # type: ignore[name-defined]
    """Register all exception handlers on the FastAPI app."""
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
