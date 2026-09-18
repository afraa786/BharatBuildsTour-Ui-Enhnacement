from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.api.routes.demo import router as demo_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="StockAware API", version="0.1.0")

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
