"""Admin panel routes: server-rendered HTML (Jinja2 + htmx). Everything under /admin."""

import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.config import get_settings
from app.db import execute, fetch_all, fetch_one
from app.places.service import ALMATY_TZ
from app.providers.storage import media_url
from app.submissions import moderation

from . import auth, service, sql

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
router = APIRouter(prefix="/admin", include_in_schema=False)

KZT_SUFFIX = " ₸"


def _display_name(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return ""
    return row.get("name_ru") or row.get("name_en") or row.get("name_kk") or "(без названия)"


def _kzt(value: Any) -> str:
    return "—" if value is None else f"{int(value):,}".replace(",", " ") + KZT_SUFFIX


templates.env.globals.update(
    display_name=_display_name,
    kzt=_kzt,
    WEEKDAY_LABELS=service.WEEKDAY_LABELS,
    KINDS=service.KINDS,
    SETTINGS=service.SETTINGS,
    STATUSES=service.STATUSES,
)


templates.env.filters["zip"] = lambda a, b: list(zip(a, b))


class AdminLoginRequired(Exception):
    pass


class AdminError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass
class PostCtx:
    session: auth.AdminSession
    form: Dict[str, str]


# ---------------------------------------------------------------- helpers


def db(request: Request):
    return request.app.state.db.transaction()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/admin",
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env != "dev",
    )


def render(
    request: Request,
    name: str,
    session: Optional[auth.AdminSession] = None,
    status: int = 200,
    **ctx: Any,
) -> HTMLResponse:
    ctx.update(
        session=session,
        csrf=session.csrf if session else ctx.get("csrf", ""),
        admin_email=session.email if session else None,
    )
    return templates.TemplateResponse(request, name, ctx, status_code=status)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def need_uuid(raw: str) -> str:
    value = service.parse_uuid(raw)
    if value is None:
        raise AdminError(404, "Не найдено")
    return value


async def admin_get(request: Request) -> auth.AdminSession:
    async with db(request) as conn:
        session = await auth.load_session(conn, request.cookies.get(auth.COOKIE_NAME))
    if session is None:
        raise AdminLoginRequired()
    return session


async def admin_post(request: Request) -> PostCtx:
    """Authenticated POST with a valid per-session CSRF token."""
    session = await admin_get(request)
    raw = await request.form()
    form = {k: v for k, v in raw.items() if isinstance(v, str)}
    if not auth.tokens_equal(form.get("csrf_token"), session.csrf):
        raise AdminError(403, "Недействительный CSRF-токен. Обновите страницу и повторите.")
    return PostCtx(session=session, form=form)


GET_ADMIN = Depends(admin_get)
POST_ADMIN = Depends(admin_post)


def is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


# ---------------------------------------------------------------- login / logout


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    async with db(request) as conn:
        session = await auth.load_session(conn, request.cookies.get(auth.COOKIE_NAME))
    if session:
        return redirect("/admin")
    token = secrets.token_urlsafe(24)
    response = render(request, "login.html", csrf=token, error=None, email="")
    set_cookie(response, auth.LOGIN_CSRF_COOKIE, token, 3600)
    return response


@router.post("/login")
async def login_submit(request: Request):
    raw = await request.form()
    form = {k: v for k, v in raw.items() if isinstance(v, str)}
    cookie = request.cookies.get(auth.LOGIN_CSRF_COOKIE)
    if not auth.tokens_equal(form.get("csrf_token"), cookie):
        raise AdminError(403, "Недействительный CSRF-токен. Обновите страницу и повторите.")
    settings = get_settings()
    email = form.get("email", "")
    async with db(request) as conn:
        result = await auth.login(
            conn,
            email,
            form.get("password", "")[: auth.MAX_PASSWORD_LEN + 1],
            client_ip(request),
            settings.admin_login_max_failures,
            settings.admin_login_window_min,
        )
    if not result.ok:
        message = (
            "Слишком много попыток входа. Подождите и попробуйте позже."
            if result.rate_limited
            else "Неверный e-mail или пароль"
        )
        return render(
            request,
            "login.html",
            status=429 if result.rate_limited else 401,
            csrf=cookie or "",
            error=message,
            email=email[:320],
        )
    response = redirect("/admin")
    set_cookie(response, auth.COOKIE_NAME, result.token, auth.SESSION_HOURS * 3600)
    response.delete_cookie(auth.LOGIN_CSRF_COOKIE, path="/admin")
    return response


@router.post("/logout")
async def logout(request: Request, ctx: PostCtx = POST_ADMIN):
    async with db(request) as conn:
        await auth.logout(conn, ctx.session.token)
    response = redirect("/admin/login")
    response.delete_cookie(auth.COOKIE_NAME, path="/admin")
    return response


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def index(request: Request, session: auth.AdminSession = GET_ADMIN):
    async with db(request) as conn:
        counts = await fetch_one(conn, sql.COUNTS)
    return render(request, "index.html", session, counts=counts)


# ---------------------------------------------------------------- moderation (Ш-45)


@router.get("/moderation", response_class=HTMLResponse)
async def moderation_queue(
    request: Request, session: auth.AdminSession = GET_ADMIN, done: str = ""
):
    async with db(request) as conn:
        data = await moderation.queue(conn)
    return render(request, "moderation.html", session, media_url=media_url, done=done, **data)


@router.post("/moderation/{submission_id}/{decision}")
async def moderation_decide(
    request: Request, submission_id: str, decision: str, ctx: PostCtx = POST_ADMIN
):
    if decision not in ("approve", "reject"):
        raise AdminError(404, "Не найдено")
    submission_id = need_uuid(submission_id)
    try:
        async with db(request) as conn:
            await moderation.decide(
                conn, ctx.session.admin_id, UUID(submission_id), decision == "approve"
            )
    except moderation.AlreadyDecided:
        return redirect("/admin/moderation?done=already")
    return redirect("/admin/moderation?done=" + decision)


# ---------------------------------------------------------------- places


async def _category_options(conn):
    return await fetch_all(conn, sql.CATEGORIES_OPTIONS)


@router.get("/places", response_class=HTMLResponse)
async def places_list(
    request: Request,
    q: str = "",
    category: str = "",
    status: str = "",
    page: str = "1",
    session: auth.AdminSession = GET_ADMIN,
):
    async with db(request) as conn:
        result = await service.list_places(conn, q, category, status, service.page_number(page))
        categories = await _category_options(conn)
    ctx = dict(result, q=q, category=category, status_f=status, categories=categories)
    template = "_places_results.html" if is_htmx(request) else "places.html"
    return render(request, template, session, **ctx)


@router.get("/places/picker", response_class=HTMLResponse)
async def place_picker(request: Request, q: str = "", session: auth.AdminSession = GET_ADMIN):
    pattern = service.like_pattern(q)
    rows = []
    if pattern:
        async with db(request) as conn:
            rows = await fetch_all(conn, sql.PLACE_PICKER, (pattern, pattern, pattern, 10))
    return render(request, "_picker.html", session, rows=rows, q=q)


def place_form_values(place: Dict[str, Any]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for field in service.PLACE_FIELDS:
        raw = place[field]
        if isinstance(raw, bool):
            values[field] = "on" if raw else ""
        else:
            values[field] = "" if raw is None else str(raw)
    for weekday in range(7):
        values[f"hours_{weekday}"] = service.format_hours_day(place["hours"], weekday)
    return values


async def _place_page(
    request: Request,
    session: auth.AdminSession,
    place: Dict[str, Any],
    form: Dict[str, str],
    errors: Dict[str, str],
    status: int = 200,
    saved: Optional[str] = None,
    photo_error: Optional[str] = None,
):
    async with db(request) as conn:
        categories = await _category_options(conn)
    return render(
        request,
        "place_form.html",
        session,
        status=status,
        place=place,
        f=form,
        errors=errors,
        categories=categories,
        saved=saved,
        photo_error=photo_error,
    )


@router.get("/places/{place_id}", response_class=HTMLResponse)
async def place_edit(
    request: Request,
    place_id: str,
    saved: str = "",
    session: auth.AdminSession = GET_ADMIN,
):
    place_id = need_uuid(place_id)
    async with db(request) as conn:
        place = await service.get_place(conn, place_id)
    if place is None:
        raise AdminError(404, "Место не найдено")
    return await _place_page(
        request, session, place, place_form_values(place), {}, saved=saved or None
    )


@router.post("/places/{place_id}")
async def place_save(request: Request, place_id: str, ctx: PostCtx = POST_ADMIN):
    place_id = need_uuid(place_id)
    async with db(request) as conn:
        try:
            marks, errors, _values, _hours = await service.save_place(conn, place_id, ctx.form)
        except LookupError:
            raise AdminError(404, "Место не найдено") from None
        place = await service.get_place(conn, place_id)
    if errors:
        return await _place_page(request, ctx.session, place, ctx.form, errors, status=422)
    return redirect(f"/admin/places/{place_id}?saved={'1' if marks else 'nochange'}")


@router.post("/places/{place_id}/photos")
async def place_photo_add(request: Request, place_id: str, ctx: PostCtx = POST_ADMIN):
    place_id = need_uuid(place_id)
    key, err = service.validate_storage_key(ctx.form.get("storage_key"))
    async with db(request) as conn:
        place = await service.get_place(conn, place_id)
        if place is None:
            raise AdminError(404, "Место не найдено")
        if err is None:
            await execute(conn, sql.PLACE_PHOTO_INSERT, (place_id, key))
    if err:
        return await _place_page(
            request, ctx.session, place, place_form_values(place), {}, status=422, photo_error=err
        )
    return redirect(f"/admin/places/{place_id}?saved=photo")


@router.post("/places/{place_id}/photos/{photo_id}/delete")
async def place_photo_delete(
    request: Request, place_id: str, photo_id: str, ctx: PostCtx = POST_ADMIN
):
    place_id, photo_id = need_uuid(place_id), need_uuid(photo_id)
    async with db(request) as conn:
        await execute(conn, sql.PLACE_PHOTO_DELETE, (photo_id, place_id))
    return redirect(f"/admin/places/{place_id}?saved=photo")


# ---------------------------------------------------------------- categories


@router.get("/categories", response_class=HTMLResponse)
async def categories_list(request: Request, session: auth.AdminSession = GET_ADMIN):
    async with db(request) as conn:
        rows = await fetch_all(conn, sql.CATEGORIES_LIST)
    return render(request, "categories.html", session, rows=rows)


@router.get("/categories/{category_id}", response_class=HTMLResponse)
async def category_edit(
    request: Request,
    category_id: str,
    saved: str = "",
    session: auth.AdminSession = GET_ADMIN,
):
    category_id = need_uuid(category_id)
    async with db(request) as conn:
        row = await fetch_one(conn, sql.CATEGORY_GET, (category_id,))
    if row is None:
        raise AdminError(404, "Категория не найдена")
    form = {
        "name_ru": row["name_ru"],
        "name_en": row["name_en"],
        "outdoor": "on" if row["outdoor"] else "",
        "sort_order": str(row["sort_order"]),
    }
    return render(request, "category_form.html", session, row=row, f=form, errors={}, saved=saved)


@router.post("/categories/{category_id}")
async def category_save(request: Request, category_id: str, ctx: PostCtx = POST_ADMIN):
    category_id = need_uuid(category_id)
    values, errors = service.validate_category(ctx.form)
    async with db(request) as conn:
        row = await fetch_one(conn, sql.CATEGORY_GET, (category_id,))
        if row is None:
            raise AdminError(404, "Категория не найдена")
        if not errors:
            await execute(
                conn,
                sql.CATEGORY_UPDATE,
                (
                    values["name_ru"],
                    values["name_en"],
                    values["outdoor"],
                    values["sort_order"],
                    category_id,
                ),
            )
    if errors:
        return render(
            request,
            "category_form.html",
            ctx.session,
            status=422,
            row=row,
            f=ctx.form,
            errors=errors,
            saved="",
        )
    return redirect(f"/admin/categories/{category_id}?saved=1")


# ---------------------------------------------------------------- curated routes


@router.get("/routes", response_class=HTMLResponse)
async def routes_list(request: Request, session: auth.AdminSession = GET_ADMIN):
    async with db(request) as conn:
        rows = await fetch_all(conn, sql.ROUTES_LIST)
    return render(request, "routes.html", session, rows=rows)


@router.get("/routes/new", response_class=HTMLResponse)
async def route_new(request: Request, session: auth.AdminSession = GET_ADMIN):
    return render(request, "route_new.html", session, f={}, errors={})


@router.post("/routes/new")
async def route_create(request: Request, ctx: PostCtx = POST_ADMIN):
    values, errors = service.validate_route(ctx.form)
    if errors:
        return render(request, "route_new.html", ctx.session, status=422, f=ctx.form, errors=errors)
    async with db(request) as conn:
        row = await fetch_one(
            conn,
            sql.ROUTE_INSERT,
            (
                values["title_ru"],
                values["title_en"],
                values["description_ru"],
                values["description_en"],
            ),
        )
    return redirect(f"/admin/routes/{row['id']}?saved=created")


async def _route_page(
    request: Request,
    session: auth.AdminSession,
    route_id: str,
    form: Optional[Dict[str, str]] = None,
    errors: Optional[Dict[str, str]] = None,
    status: int = 200,
    saved: Optional[str] = None,
    notice: Optional[str] = None,
):
    async with db(request) as conn:
        route = await fetch_one(conn, sql.ROUTE_GET, (route_id,))
        if route is None:
            raise AdminError(404, "Маршрут не найден")
        items = await fetch_all(conn, sql.ROUTE_ITEMS, (route_id,))
    if form is None:
        form = {
            k: (route[k] or "")
            for k in ("title_ru", "title_en", "description_ru", "description_en")
        }
    return render(
        request,
        "route_form.html",
        session,
        status=status,
        route=route,
        items=items,
        f=form,
        errors=errors or {},
        saved=saved,
        notice=notice,
    )


@router.get("/routes/{route_id}", response_class=HTMLResponse)
async def route_edit(
    request: Request,
    route_id: str,
    saved: str = "",
    session: auth.AdminSession = GET_ADMIN,
):
    return await _route_page(request, session, need_uuid(route_id), saved=saved or None)


@router.post("/routes/{route_id}")
async def route_save(request: Request, route_id: str, ctx: PostCtx = POST_ADMIN):
    route_id = need_uuid(route_id)
    values, errors = service.validate_route(ctx.form)
    if errors:
        return await _route_page(
            request, ctx.session, route_id, form=ctx.form, errors=errors, status=422
        )
    async with db(request) as conn:
        if not await fetch_one(conn, sql.ROUTE_GET, (route_id,)):
            raise AdminError(404, "Маршрут не найден")
        await execute(
            conn,
            sql.ROUTE_UPDATE,
            (
                values["title_ru"],
                values["title_en"],
                values["description_ru"],
                values["description_en"],
                route_id,
            ),
        )
    return redirect(f"/admin/routes/{route_id}?saved=1")


@router.get("/routes/{route_id}/place-search", response_class=HTMLResponse)
async def route_place_search(
    request: Request,
    route_id: str,
    q: str = "",
    session: auth.AdminSession = GET_ADMIN,
):
    route_id = need_uuid(route_id)
    pattern = service.like_pattern(q)
    rows = []
    if pattern:
        async with db(request) as conn:
            rows = await fetch_all(conn, sql.PLACE_PICKER, (pattern, pattern, pattern, 10))
    return render(request, "_route_search.html", session, rows=rows, q=q, route_id=route_id)


@router.post("/routes/{route_id}/places")
async def route_add_place(request: Request, route_id: str, ctx: PostCtx = POST_ADMIN):
    route_id = need_uuid(route_id)
    place_id = service.parse_uuid(ctx.form.get("place_id"))
    async with db(request) as conn:
        try:
            err = (
                await service.add_route_place(conn, route_id, place_id)
                if place_id
                else "Место не найдено"
            )
        except LookupError:
            raise AdminError(404, "Маршрут не найден") from None
    if err:
        return await _route_page(request, ctx.session, route_id, status=422, notice=err)
    return redirect(f"/admin/routes/{route_id}?saved=place")


@router.post("/routes/{route_id}/items/{item_id}/move")
async def route_move_item(request: Request, route_id: str, item_id: str, ctx: PostCtx = POST_ADMIN):
    route_id, item_id = need_uuid(route_id), need_uuid(item_id)
    async with db(request) as conn:
        await service.move_route_item(conn, route_id, item_id, ctx.form.get("direction", ""))
    return redirect(f"/admin/routes/{route_id}")


@router.post("/routes/{route_id}/items/{item_id}/remove")
async def route_remove_item(
    request: Request, route_id: str, item_id: str, ctx: PostCtx = POST_ADMIN
):
    route_id, item_id = need_uuid(route_id), need_uuid(item_id)
    async with db(request) as conn:
        await service.remove_route_item(conn, route_id, item_id)
    return redirect(f"/admin/routes/{route_id}")


@router.post("/routes/{route_id}/status")
async def route_status(request: Request, route_id: str, ctx: PostCtx = POST_ADMIN):
    route_id = need_uuid(route_id)
    async with db(request) as conn:
        if not await fetch_one(conn, sql.ROUTE_GET, (route_id,)):
            raise AdminError(404, "Маршрут не найден")
        err = await service.set_route_status(conn, route_id, ctx.form.get("status", ""))
    if err:
        return await _route_page(request, ctx.session, route_id, status=422, notice=err)
    return redirect(f"/admin/routes/{route_id}?saved=status")


@router.post("/routes/{route_id}/delete")
async def route_delete(request: Request, route_id: str, ctx: PostCtx = POST_ADMIN):
    route_id = need_uuid(route_id)
    async with db(request) as conn:
        await execute(conn, sql.ROUTE_DELETE, (route_id,))
    return redirect("/admin/routes")


# ---------------------------------------------------------------- tariffs


async def _tariff_page(request, session, form=None, errors=None):
    today = datetime.now(ALMATY_TZ).date()
    async with db(request) as conn:
        rows = await fetch_all(conn, sql.TARIFFS_LIST, (today,))
    return render(
        request,
        "tariffs.html",
        session,
        status=422 if errors else 200,
        rows=rows,
        today=today,
        modes=service.TARIFF_MODES,
        fields=service.TARIFF_FIELDS,
        f=form or {"valid_from": today.isoformat(), "approximate": "on"},
        errors=errors or {},
    )


@router.get("/tariffs", response_class=HTMLResponse)
async def tariffs_list(request: Request, session: auth.AdminSession = GET_ADMIN):
    return await _tariff_page(request, session)


@router.post("/tariffs")
async def tariff_create(request: Request, ctx: PostCtx = POST_ADMIN):
    values, errors = service.validate_tariff(ctx.form)
    if errors:
        return await _tariff_page(request, ctx.session, ctx.form, errors)
    async with db(request) as conn:
        await execute(
            conn,
            sql.TARIFF_INSERT,
            (
                values["mode"],
                values["valid_from"],
                values["base_kzt"],
                values["per_min_kzt"],
                values["per_km_kzt"],
                values["approximate"],
                values["source"],
            ),
        )
    return redirect("/admin/tariffs")


# ---------------------------------------------------------------- events


def _local_str(value) -> str:
    return value.strftime("%Y-%m-%dT%H:%M") if value else ""


async def _event_form_ctx(conn, form: Dict[str, str]) -> Dict[str, Any]:
    categories = await _category_options(conn)
    place = None
    place_id = service.parse_uuid(form.get("place_id"))
    if place_id:
        place = await fetch_one(conn, sql.PLACE_LABEL, (place_id,))
    return {"categories": categories, "place_label": _display_name(place) if place else ""}


@router.get("/events", response_class=HTMLResponse)
async def events_list(request: Request, session: auth.AdminSession = GET_ADMIN):
    async with db(request) as conn:
        rows = await fetch_all(conn, sql.EVENTS_LIST)
    return render(request, "events.html", session, rows=rows)


@router.get("/events/new", response_class=HTMLResponse)
async def event_new(request: Request, session: auth.AdminSession = GET_ADMIN):
    async with db(request) as conn:
        extra = await _event_form_ctx(conn, {})
    return render(request, "event_form.html", session, event=None, f={}, errors={}, **extra)


@router.post("/events/new")
async def event_create(request: Request, ctx: PostCtx = POST_ADMIN):
    values, errors = service.validate_event(ctx.form)
    async with db(request) as conn:
        await service.check_event_refs(conn, values, errors)
        if not errors:
            row = await fetch_one(conn, sql.EVENT_INSERT, values)
        extra = await _event_form_ctx(conn, ctx.form)
    if errors:
        return render(
            request,
            "event_form.html",
            ctx.session,
            status=422,
            event=None,
            f=ctx.form,
            errors=errors,
            **extra,
        )
    return redirect(f"/admin/events/{row['id']}?saved=created")


@router.get("/events/{event_id}", response_class=HTMLResponse)
async def event_edit(
    request: Request,
    event_id: str,
    saved: str = "",
    session: auth.AdminSession = GET_ADMIN,
):
    event_id = need_uuid(event_id)
    async with db(request) as conn:
        event = await fetch_one(conn, sql.EVENT_GET, (event_id,))
        if event is None:
            raise AdminError(404, "Мероприятие не найдено")
        form = {
            "place_id": str(event["place_id"] or ""),
            "title_ru": event["title_ru"],
            "title_en": event["title_en"] or "",
            "starts_at": _local_str(event["starts_local"]),
            "ends_at": _local_str(event["ends_local"]),
            "price_kzt": "" if event["price_kzt"] is None else str(event["price_kzt"]),
            "category_id": str(event["category_id"] or ""),
            "is_promoted": "on" if event["is_promoted"] else "",
            "sponsor": event["sponsor"] or "",
        }
        extra = await _event_form_ctx(conn, form)
    return render(
        request,
        "event_form.html",
        session,
        event=event,
        f=form,
        errors={},
        saved=saved,
        **extra,
    )


@router.post("/events/{event_id}")
async def event_save(request: Request, event_id: str, ctx: PostCtx = POST_ADMIN):
    event_id = need_uuid(event_id)
    values, errors = service.validate_event(ctx.form)
    async with db(request) as conn:
        event = await fetch_one(conn, sql.EVENT_GET, (event_id,))
        if event is None:
            raise AdminError(404, "Мероприятие не найдено")
        await service.check_event_refs(conn, values, errors)
        if not errors:
            await execute(conn, sql.EVENT_UPDATE, dict(values, id=event_id))
        extra = await _event_form_ctx(conn, ctx.form)
    if errors:
        return render(
            request,
            "event_form.html",
            ctx.session,
            status=422,
            event=event,
            f=ctx.form,
            errors=errors,
            **extra,
        )
    return redirect(f"/admin/events/{event_id}?saved=1")


@router.post("/events/{event_id}/delete")
async def event_delete(request: Request, event_id: str, ctx: PostCtx = POST_ADMIN):
    event_id = need_uuid(event_id)
    async with db(request) as conn:
        await execute(conn, sql.EVENT_DELETE, (event_id,))
    return redirect("/admin/events")


# ---------------------------------------------------------------- mounting

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'"
    ),
}


def install_admin(app: FastAPI) -> None:
    app.mount("/admin/static", StaticFiles(directory=str(BASE / "static")), name="admin-static")
    app.include_router(router)

    @app.exception_handler(AdminLoginRequired)
    async def _login_required(request: Request, exc: AdminLoginRequired):
        if is_htmx(request):
            return Response(status_code=401, headers={"HX-Redirect": "/admin/login"})
        return redirect("/admin/login")

    @app.exception_handler(AdminError)
    async def _admin_error(request: Request, exc: AdminError):
        session = None
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": exc.message, "status": exc.status_code, "session": session, "csrf": ""},
            status_code=exc.status_code,
        )

    @app.middleware("http")
    async def _admin_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/admin"):
            for key, value in SECURITY_HEADERS.items():
                if request.url.path.startswith("/admin/static") and key == "Cache-Control":
                    continue
                response.headers.setdefault(key, value)
        return response
