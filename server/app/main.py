import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__, observability
from app.admin.api import install_admin
from app.analytics.api import make_limiters as make_analytics_limiters
from app.analytics.api import router as analytics_router
from app.auth import keys
from app.auth.api import router as auth_router
from app.auth.apple import router as apple_router
from app.auth.otp_api import router as otp_router
from app.bookings.api import router as bookings_router
from app.chat.api import router as chat_router
from app.chat.deps import make_limiters
from app.chat.guest import router as guest_chat_router
from app.config import get_settings
from app.crowd.api import router as crowd_router
from app.db import Database
from app.devices.api import router as devices_router
from app.errors import install_error_handlers
from app.events.api import router as events_router
from app.favorites.api import router as favorites_router
from app.geocode.api import LIMIT_PER_MINUTE as GEOCODE_LIMIT
from app.geocode.api import router as geocode_router
from app.logging_setup import setup_logging
from app.middleware import RequestIdMiddleware
from app.places.api import router as places_router
from app.providers.storage import make_storage
from app.providers.weather import OpenMeteoProvider
from app.ratelimit import RateRule
from app.routing import make_router
from app.routing.api import router as directions_router
from app.submissions.api import router as submissions_router
from app.submissions.dev_api import router as dev_uploads_router
from app.system.api import router as system_router
from app.trips.api import router as trips_router

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    keys.validate(settings)  # missing / shared secrets outside dev and test: do not start (Ш-51)
    observability.init_error_reporting(settings)
    if settings.app_env not in ("dev", "test") and not settings.trusted_proxies:
        log.warning(
            "TRUSTED_PROXIES is empty: behind a reverse proxy every client shares the proxy's IP"
            " and per-IP limits (OTP, guest chat) will lock everybody out together"
        )
    db = Database(settings.database_url, settings.db_pool_min, settings.db_pool_max)
    async with AsyncExitStack() as stack:
        stack.push_async_callback(db.close)
        await db.open()
        app.state.db = db
        routing_provider = make_router(settings.valhalla_url)
        stack.push_async_callback(routing_provider.aclose)
        app.state.routing_provider = routing_provider
        weather_provider = OpenMeteoProvider.from_settings(db)  # forecast for builds (Ш-40)
        stack.push_async_callback(weather_provider.aclose)
        app.state.weather_provider = weather_provider
        storage = make_storage(settings)
        if storage is not None:
            stack.push_async_callback(storage.aclose)
        app.state.storage = storage
        log.info("api started", extra={"env": settings.app_env, "version": __version__})
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    public_docs = settings.app_env in ("dev", "test")  # no interactive docs on staging / prod
    app = FastAPI(
        title="Jol API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if public_docs else None,
        redoc_url="/redoc" if public_docs else None,
        openapi_url="/openapi.json" if public_docs else None,
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.state.chat_limiters = make_limiters(settings)
    app.state.analytics_limiters = make_analytics_limiters(settings)
    app.state.geocode_limiter = RateRule("geocode", GEOCODE_LIMIT, 60)
    app.include_router(system_router)
    app.include_router(auth_router)
    app.include_router(otp_router)
    app.include_router(apple_router)
    app.include_router(places_router)
    app.include_router(geocode_router)
    app.include_router(directions_router)
    app.include_router(guest_chat_router)
    app.include_router(chat_router)
    app.include_router(trips_router)
    app.include_router(devices_router)
    app.include_router(favorites_router)
    app.include_router(submissions_router)
    app.include_router(crowd_router)
    app.include_router(events_router)
    app.include_router(bookings_router)
    app.include_router(analytics_router)
    app.include_router(dev_uploads_router)
    if settings.storage_provider == "local" and settings.app_env in ("dev", "test"):
        local = make_storage(settings)
        local.root.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=str(local.root)), name="media")  # dev only
    install_admin(app)
    return app


app = create_app()
