from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.errors import install_error_handlers
from backend.app.api.routes import router
from backend.app.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(title="Myroll Local Backend", version=resolved.app_version)
    app.state.settings = resolved
    install_error_handlers(app)
    app.include_router(router)
    return app
