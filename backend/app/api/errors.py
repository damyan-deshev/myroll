from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


def api_error(status_code: int, code: str, message: str, details: list[dict] | None = None) -> HTTPException:
    payload: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return HTTPException(status_code=status_code, detail=payload)


def error_response(status_code: int, code: str, message: str, details: list[dict] | None = None) -> JSONResponse:
    body: dict[str, object] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details  # type: ignore[index]
    return JSONResponse(status_code=status_code, content=body)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        return error_response(
            status_code=exc.status_code,
            code=str(exc.detail["code"]),
            message=str(exc.detail["message"]),
            details=exc.detail.get("details"),  # type: ignore[arg-type]
        )
    if exc.status_code == 404:
        return error_response(404, "not_found", "Not found")
    return error_response(exc.status_code, "http_error", str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "loc": [str(part) for part in error.get("loc", [])],
            "message": str(error.get("msg", "Invalid value")),
            "type": str(error.get("type", "validation_error")),
        }
        for error in exc.errors()
    ]
    return error_response(422, "validation_error", "Request validation failed", details)


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return error_response(409, "database_integrity_error", "Database integrity error")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
