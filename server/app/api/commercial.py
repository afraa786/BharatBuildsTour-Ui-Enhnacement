import logging
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute

logger = logging.getLogger(__name__)


class CommercialError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _request_id() -> str:
    return f"req_{uuid4().hex}"


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id or _request_id(),
    }
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


class CommercialRoute(APIRoute):
    """Apply the Fareed error contract without changing Rehbar-owned routes."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            request_id = _request_id()
            try:
                return await original(request)
            except CommercialError as exc:
                return error_response(
                    status_code=exc.status_code,
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                    request_id=request_id,
                )
            except RequestValidationError as exc:
                errors = [
                    {
                        "location": [str(part) for part in error["loc"]],
                        "message": error["msg"],
                        "type": error["type"],
                    }
                    for error in exc.errors()
                ]
                messages = {error["message"] for error in errors}
                message = messages.pop() if len(messages) == 1 else "The request failed validation."
                return error_response(
                    status_code=422,
                    code="VALIDATION_ERROR",
                    message=message,
                    details={"errors": errors},
                    request_id=request_id,
                )
            except Exception as exc:  # pragma: no cover - defensive transport boundary
                logger.error(
                    "Unhandled commercial API failure request_id=%s error_type=%s",
                    request_id,
                    type(exc).__name__,
                )
                return error_response(
                    status_code=500,
                    code="INTERNAL_ERROR",
                    message="An internal error occurred.",
                    request_id=request_id,
                )

        return handler
