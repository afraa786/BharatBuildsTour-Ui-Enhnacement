import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router
from app.api.routes.demo import router as demo_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="StockAware API", version="0.1.0")

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        """Answer unhandled errors with a JSON 500 that still carries CORS headers.

        Starlette builds the response for an unhandled exception in its outermost
        error middleware, i.e. outside the CORS middleware, so the browser cannot
        read it and the UI reports a bare "Failed to fetch" instead of the real
        failure. Echoing the allowed origin keeps 500s visible to the client.
        """
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        origin = request.headers.get("origin")
        headers: dict[str, str] = {}
        if origin and origin in settings.cors_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}},
            headers=headers,
        )

    @app.middleware("http")
    async def legacy_commercial_paths(request: Request, call_next):
        """Preserve internal reads where owner and commercial paths overlap."""
        if not request.headers.get("authorization", "").lower().startswith("bearer "):
            path = request.scope["path"]
            if request.method == "GET" and (path == "/products" or path.startswith("/invoices/")):
                request.scope["path"] = "/internal" + path
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Idempotency-Key",
            "X-Internal-Service-Token",
        ],
    )
    app.include_router(router)
    if settings.environment in {"local", "development", "test"}:
        app.include_router(demo_router)
    return app


app = create_app()
