"""FastAPI app factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app import __version__
from app.api.routes import admin, analyses, field, health, scene, watch
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Build the application with routes, CORS and error handlers."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="SENTINEL API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # /tracks is ~0.5 MB of JSON; gzip cuts it ~5x.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    register_exception_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(scene.router, prefix="/api")
    app.include_router(analyses.router, prefix="/api")
    app.include_router(watch.router, prefix="/api")
    app.include_router(field.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    return app


app = create_app()
