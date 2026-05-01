from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.errors import install_error_handlers
from backend.app.api.routes import router
from backend.app.settings import Settings, get_settings


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CROSS_SITE_REJECTION = {
    "error": {
        "code": "cross_site_request_rejected",
        "message": "Cross-site unsafe requests are not allowed",
    }
}


def _api_origin(host: str, port: int) -> str | None:
    if not host or host == "0.0.0.0":
        return None
    scheme = "http"
    return f"{scheme}://{host}:{port}"


def _normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip().rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}"


def _allowed_request_origins(settings: Settings) -> set[str]:
    origins = {_normalize_origin(origin) for origin in settings.allowed_origins}
    for host in settings.allowed_hosts:
        origin = _api_origin(host, settings.port)
        if origin:
            origins.add(_normalize_origin(origin))
    return origins


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(title="Myroll Local Backend", version=resolved.app_version)
    app.state.settings = resolved
    allowed_origins = sorted(_allowed_request_origins(resolved))

    @app.middleware("http")
    async def reject_cross_site_unsafe_requests(request, call_next):  # noqa: ANN001
        if request.method.upper() in UNSAFE_METHODS:
            origin = request.headers.get("origin")
            fetch_site = request.headers.get("sec-fetch-site")
            if origin and _normalize_origin(origin) not in allowed_origins:
                return JSONResponse(status_code=403, content=CROSS_SITE_REJECTION)
            if not origin and fetch_site == "cross-site":
                return JSONResponse(status_code=403, content=CROSS_SITE_REJECTION)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(resolved.allowed_hosts))
    install_error_handlers(app)
    app.include_router(router)
    return app
