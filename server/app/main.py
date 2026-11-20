import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.admin.api import install_admin
from app.config import get_settings
from app.db import Database
from app.errors import install_error_handlers
from app.logging_setup import setup_logging
from app.middleware import RequestIdMiddleware
from app.places.api import router as places_router
from app.system.api import router as system_router

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = Database(settings.database_url, settings.db_pool_min, settings.db_pool_max)
    await db.open()
    app.state.db = db
    log.info("api started", extra={"env": settings.app_env, "version": __version__})
    try:
        yield
    finally:
        await db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(title="Jol API", version=__version__, lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(system_router)
    app.include_router(places_router)
    install_admin(app)
    return app


app = create_app()
