from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from farebeacon.api.schemas import ErrorCode


class AppError(Exception):
    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers


def error_payload(request: Request, error: AppError) -> dict[str, Any]:
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        },
        "meta": {"request_id": request.state.request_id},
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error_payload(request, error),
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        app_error = AppError(
            code="VALIDATION_ERROR",
            message="The request payload is invalid.",
            status_code=422,
            details={"errors": jsonable_encoder(error.errors())},
        )
        return JSONResponse(status_code=422, content=error_payload(request, app_error))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logging.getLogger("farebeacon.api").exception(
            "unhandled request error",
            extra={"request_id": request.state.request_id},
        )
        app_error = AppError(
            code="INTERNAL_ERROR",
            message="An unexpected internal error occurred.",
            status_code=500,
        )
        return JSONResponse(status_code=500, content=error_payload(request, app_error))
