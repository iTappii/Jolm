"""Admin logic: input validation (pure functions) and DB operations (raw SQL from sql.py).

Validation functions take a mapping of submitted form strings and return (values, errors);
`errors` maps a field name to a Russian message and is empty when the input is valid.
"""

import json
import re
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Tuple

from app.db import execute, fetch_all, fetch_one
from app.planner.area import ALMATY_BBOX

from . import sql

Errors = Dict[str, str]

KINDS = ("landmark", "venue", "nature", "accommodation", "event_venue")
SETTINGS = ("indoor", "outdoor", "mixed")
STATUSES = ("active", "hidden", "closed")
WEEKDAY_LABELS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

# Hard-coded whitelist of editable places columns == names recorded in places.manual_override.
PLACE_FIELDS = (
    "name_ru",
    "name_en",
    "name_kk",
    "description_ru",
    "description_en",
    "category_id",
    "kind",
    "setting",
    "typical_visit_min",
    "entry_price_kzt",
    "avg_check_kzt",
    "price_per_night_kzt",
    "is_public",
    "is_mountain",
    "elevation_m",
    "popularity",
    "status",
)
HOURS_FIELD = "hours"  # same marker the OSM importer checks (data/osm/upsert.py)

MAX_MONEY = 1_000_000_000
PAGE_SIZE = 25

_TRUE = {"on", "1", "true", "yes"}
_INTERVAL_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})$")
_ROUND_CLOCK = {"24h", "24/7", "24ч", "круглосуточно"}


# ---------------------------------------------------------------- primitives


def clean_text(raw: Optional[str], max_len: int) -> Tuple[Optional[str], Optional[str]]:
    """Strip; empty -> None. Returns (value, error)."""
    value = (raw or "").strip()
    if not value:
        return None, None
    if len(value) > max_len:
        return None, f"Не длиннее {max_len} символов"
    if "\x00" in value:
        return None, "Недопустимые символы"
    return value, None


def parse_int(
    raw: Optional[str], lo: int, hi: int, default: Optional[int] = None
) -> Tuple[Optional[int], Optional[str]]:
    value = (raw or "").strip().replace(" ", "")
    if not value:
        return default, None
    if not re.fullmatch(r"-?\d{1,12}", value):
        return None, "Нужно целое число"
    number = int(value)
    if number < lo or number > hi:
        return None, f"Допустимо от {lo} до {hi}"
    return number, None


def parse_uuid(raw: Optional[str]) -> Optional[str]:
    try:
        return str(uuid.UUID((raw or "").strip()))
    except ValueError:
        return None


def parse_bool(raw: Optional[str]) -> bool:
    return (raw or "").strip().lower() in _TRUE


def like_pattern(q: Optional[str]) -> Optional[str]:
    """ILIKE pattern with LIKE metacharacters escaped (backslash is the ESCAPE char)."""
    q = (q or "").strip()[:100]
    if not q:
        return None
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def page_number(raw: Optional[str]) -> int:
    number, err = parse_int(raw, 1, 100_000, default=1)
    return 1 if err or number is None else number


# ---------------------------------------------------------------- places validation


def validate_place(form: Mapping[str, str]) -> Tuple[Dict[str, Any], Errors]:
    values: Dict[str, Any] = {}
    errors: Errors = {}

    def text(field: str, max_len: int) -> None:
        values[field], err = clean_text(form.get(field), max_len)
        if err:
            errors[field] = err

    def number(field: str, lo: int, hi: int, default: Optional[int] = None) -> None:
        values[field], err = parse_int(form.get(field), lo, hi, default)
        if err:
            errors[field] = err

    for field in ("name_ru", "name_en", "name_kk"):
        text(field, 300)
    for field in ("description_ru", "description_en"):
        text(field, 5000)
    if not (values["name_ru"] or values["name_en"] or values["name_kk"]):
        errors["name_ru"] = "Нужно хотя бы одно название (RU, EN или KK)"

    raw_cat = (form.get("category_id") or "").strip()
    values["category_id"] = parse_uuid(raw_cat) if raw_cat else None
    if raw_cat and values["category_id"] is None:
        errors["category_id"] = "Неверная категория"

    kind = (form.get("kind") or "").strip()
    if kind not in KINDS:
        errors["kind"] = "Недопустимый тип"
    values["kind"] = kind

    setting = (form.get("setting") or "").strip()
    if setting and setting not in SETTINGS:
        errors["setting"] = "Недопустимое значение"
    values["setting"] = setting or None

    number("typical_visit_min", 1, 1440)
    number("entry_price_kzt", 0, MAX_MONEY)
    number("avg_check_kzt", 0, MAX_MONEY)
    number("price_per_night_kzt", 0, MAX_MONEY)
    number("elevation_m", -500, 9000)
    number("popularity", 0, 1_000_000, default=0)

    values["is_public"] = parse_bool(form.get("is_public"))
    values["is_mountain"] = parse_bool(form.get("is_mountain"))

    status = (form.get("status") or "").strip()
    if status not in STATUSES:
        errors["status"] = "Недопустимый статус"
    values["status"] = status
    return values, errors


def _parse_time(hh: str, mm: str) -> Optional[time]:
    h, m = int(hh), int(mm)
    if h > 23 or m > 59:
        return None
    return time(h, m)


def parse_hours_day(raw: Optional[str]) -> Tuple[List[Tuple[time, time]], Optional[str]]:
    """One interval per line (or separated by ';' / ','): '09:00-18:00'. Empty = closed/unknown.

    closes <= opens means the interval runs past midnight (same convention as place_hours).
    """
    intervals: List[Tuple[time, time]] = []
    parts = [p.strip() for p in re.split(r"[\n;,]+", raw or "") if p.strip()]
    if len(parts) > 6:
        return [], "Не более 6 интервалов в день"
    for part in parts:
        if part.lower() in _ROUND_CLOCK:
            intervals.append((time(0, 0), time(23, 59)))
            continue
        m = _INTERVAL_RE.match(part)
        if not m:
            return [], f"Неверный формат «{part}», нужно ЧЧ:ММ-ЧЧ:ММ"
        opens, closes = _parse_time(m.group(1), m.group(2)), _parse_time(m.group(3), m.group(4))
        if opens is None or closes is None:
            return [], f"Неверное время в «{part}»"
        if opens == closes:
            return [], f"Начало и конец совпадают в «{part}»"
        intervals.append((opens, closes))
    same_day = sorted(i for i in intervals if i[1] > i[0])
    for prev, cur in zip(same_day, same_day[1:]):
        if cur[0] < prev[1]:
            return [], "Интервалы пересекаются"
    return sorted(intervals), None


def validate_hours(
    form: Mapping[str, str],
) -> Tuple[List[Tuple[int, time, time]], Errors]:
    result: List[Tuple[int, time, time]] = []
    errors: Errors = {}
    for weekday in range(7):
        key = f"hours_{weekday}"
        intervals, err = parse_hours_day(form.get(key))
        if err:
            errors[key] = err
        result.extend((weekday, o, c) for o, c in intervals)
    return result, errors


def format_hours_day(rows: List[Tuple[int, time, time]], weekday: int) -> str:
    return "\n".join(f"{o:%H:%M}-{c:%H:%M}" for wd, o, c in sorted(rows) if wd == weekday)


# ---------------------------------------------------------------- places DB


async def list_places(
    conn, q: Optional[str], category_id: Optional[str], status: Optional[str], page: int
) -> Dict[str, Any]:
    pattern = like_pattern(q)
    cat = parse_uuid(category_id) if category_id else None
    st = status if status in STATUSES else None
    filt = (pattern, pattern, pattern, pattern, cat, cat, st, st)
    total = (await fetch_one(conn, sql.PLACES_COUNT, filt))["n"]
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    rows = await fetch_all(conn, sql.PLACES_LIST, filt + (PAGE_SIZE, (page - 1) * PAGE_SIZE))
    return {"rows": rows, "total": total, "page": page, "pages": pages}


async def get_place(conn, place_id: str) -> Optional[Dict[str, Any]]:
    place = await fetch_one(conn, sql.PLACE_GET, (place_id,))
    if place is None:
        return None
    hours = await fetch_all(conn, sql.PLACE_HOURS_GET, (place_id,))
    place["hours"] = [(r["weekday"], r["opens"], r["closes"]) for r in hours]
    place["photos"] = await fetch_all(conn, sql.PLACE_PHOTOS, (place_id,))
    return place


def _norm(field: str, value: Any) -> Any:
    return str(value) if field == "category_id" and value is not None else value


async def save_place(
    conn, place_id: str, form: Mapping[str, str]
) -> Tuple[Optional[List[str]], Errors, Dict[str, Any], List[Tuple[int, time, time]]]:
    """Validate and save. Returns (marked_names | None on errors, errors, values, hours).

    Every field whose value differs from the stored one is added to places.manual_override
    (plus 'hours' when the opening hours changed), so an OSM re-import cannot overwrite it.
    """
    current = await fetch_one(conn, sql.PLACE_GET, (place_id,))
    if current is None:
        raise LookupError(place_id)
    values, errors = validate_place(form)
    hours, hour_errors = validate_hours(form)
    errors.update(hour_errors)
    if values.get("category_id") and "category_id" not in errors:
        if not await fetch_one(conn, sql.CATEGORY_EXISTS, (values["category_id"],)):
            errors["category_id"] = "Категория не найдена"
    if errors:
        return None, errors, values, hours

    changed = [f for f in PLACE_FIELDS if _norm(f, current[f]) != _norm(f, values[f])]
    old_hours = await fetch_all(conn, sql.PLACE_HOURS_GET, (place_id,))
    old_hours_t = sorted((r["weekday"], r["opens"], r["closes"]) for r in old_hours)
    hours_changed = old_hours_t != sorted(hours)

    marks = list(changed) + ([HOURS_FIELD] if hours_changed else [])
    override = [x for x in (current["manual_override"] or []) if isinstance(x, str)]
    for mark in marks:
        if mark not in override:
            override.append(mark)

    if changed:
        await execute(
            conn,
            sql.PLACE_UPDATE,
            dict(values, id=place_id, manual_override=json.dumps(override)),
        )
    if hours_changed:
        await execute(conn, sql.PLACE_HOURS_DELETE, (place_id,))
        for weekday, opens, closes in hours:
            await execute(conn, sql.PLACE_HOURS_INSERT, (place_id, weekday, opens, closes))
        if not changed:
            await execute(conn, sql.PLACE_TOUCH_OVERRIDE, (json.dumps(override), place_id))
    return marks, errors, values, hours


def validate_storage_key(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    # TODO(Ш-44): real upload to S3; for now the admin pastes a storage key or an https URL.
    value, err = clean_text(raw, 500)
    if err or value is None:
        return None, err or "Укажите ключ в хранилище или URL"
    if re.search(r"\s", value):
        return None, "Без пробелов"
    if "://" in value and not value.lower().startswith("https://"):
        return None, "Допустим только https://"
    return value, None


# ---------------------------------------------------------------- categories


def validate_category(form: Mapping[str, str]) -> Tuple[Dict[str, Any], Errors]:
    values: Dict[str, Any] = {}
    errors: Errors = {}
    for field in ("name_ru", "name_en"):
        values[field], err = clean_text(form.get(field), 200)
        if err:
            errors[field] = err
        elif values[field] is None:
            errors[field] = "Обязательное поле"
    values["outdoor"] = parse_bool(form.get("outdoor"))
    values["sort_order"], err = parse_int(form.get("sort_order"), -100_000, 100_000, default=0)
    if err:
        errors["sort_order"] = err
    return values, errors


# ---------------------------------------------------------------- curated routes


def validate_route(form: Mapping[str, str]) -> Tuple[Dict[str, Any], Errors]:
    values: Dict[str, Any] = {}
    errors: Errors = {}
    for field in ("title_ru", "title_en"):
        values[field], err = clean_text(form.get(field), 200)
        if err:
            errors[field] = err
        elif values[field] is None:
            errors[field] = "Обязательное поле"
    for field in ("description_ru", "description_en"):
        values[field], err = clean_text(form.get(field), 5000)
        if err:
            errors[field] = err
    return values, errors


async def route_place_ids(conn, route_id: str) -> List[Tuple[Any, Any]]:
    rows = await fetch_all(conn, sql.ROUTE_ITEM_IDS, (route_id,))
    return [(r["id"], r["place_id"]) for r in rows]


async def _renumber(conn, route_id: str) -> None:
    # unique(route_id, ord): move out of the way first, then dense 1..n in current order
    await execute(conn, sql.ROUTE_ITEMS_SHIFT, (route_id,))
    await execute(conn, sql.ROUTE_ITEMS_RENUMBER, (route_id,))


async def add_route_place(conn, route_id: str, place_id: str) -> Optional[str]:
    """Append a place. Returns an error message or None."""
    if not await fetch_one(conn, sql.ROUTE_LOCK, (route_id,)):
        raise LookupError(route_id)
    if not await fetch_one(conn, sql.PLACE_EXISTS, (place_id,)):
        return "Место не найдено"
    ids = [str(pid) for _, pid in await route_place_ids(conn, route_id)]
    if place_id in ids:
        return "Место уже в маршруте"
    if len(ids) >= 100:
        return "Слишком много мест в маршруте"
    await execute(conn, sql.ROUTE_ITEM_APPEND, (route_id, place_id, route_id))
    return None


async def remove_route_item(conn, route_id: str, item_id: str) -> None:
    await fetch_one(conn, sql.ROUTE_LOCK, (route_id,))
    await execute(conn, sql.ROUTE_ITEM_DELETE, (item_id, route_id))
    await _renumber(conn, route_id)


async def move_route_item(conn, route_id: str, item_id: str, direction: str) -> None:
    await fetch_one(conn, sql.ROUTE_LOCK, (route_id,))
    rows = await fetch_all(conn, sql.ROUTE_ITEM_IDS, (route_id,))
    order = [str(r["id"]) for r in rows]
    if item_id not in order or direction not in ("up", "down"):
        return
    i = order.index(item_id)
    j = i - 1 if direction == "up" else i + 1
    if not 0 <= j < len(rows):
        return
    a, b = rows[i], rows[j]
    # swap ords through a temporary value (unique constraint is checked per row)
    await execute(conn, sql.ROUTE_ITEM_SET_ORD, (-1, a["id"]))
    await execute(conn, sql.ROUTE_ITEM_SET_ORD, (a["ord"], b["id"]))
    await execute(conn, sql.ROUTE_ITEM_SET_ORD, (b["ord"], a["id"]))


async def set_route_status(conn, route_id: str, status: str) -> Optional[str]:
    if status not in ("draft", "published"):
        return "Недопустимый статус"
    if status == "published" and not await route_place_ids(conn, route_id):
        return "Нельзя опубликовать маршрут без мест"
    await execute(conn, sql.ROUTE_SET_STATUS, (status, route_id))
    return None


# ---------------------------------------------------------------- events

_DT_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M")


def parse_local_dt(raw: Optional[str]) -> Optional[datetime]:
    value = (raw or "").strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def validate_event(form: Mapping[str, str]) -> Tuple[Dict[str, Any], Errors]:
    values: Dict[str, Any] = {}
    errors: Errors = {}
    values["title_ru"], err = clean_text(form.get("title_ru"), 300)
    if err:
        errors["title_ru"] = err
    elif values["title_ru"] is None:
        errors["title_ru"] = "Обязательное поле"
    values["title_en"], err = clean_text(form.get("title_en"), 300)
    if err:
        errors["title_en"] = err
    values["sponsor"], err = clean_text(form.get("sponsor"), 200)
    if err:
        errors["sponsor"] = err
    for field in ("description_ru", "description_en"):
        values[field], err = clean_text(form.get(field), 2000)
        if err:
            errors[field] = err

    starts = parse_local_dt(form.get("starts_at"))
    if starts is None:
        errors["starts_at"] = "Укажите дату и время начала"
    values["starts_at"] = starts
    raw_end = (form.get("ends_at") or "").strip()
    ends = parse_local_dt(raw_end) if raw_end else None
    if raw_end and ends is None:
        errors["ends_at"] = "Неверная дата"
    elif ends and starts and ends < starts:
        errors["ends_at"] = "Окончание раньше начала"
    values["ends_at"] = ends

    values["price_kzt"], err = parse_int(form.get("price_kzt"), 0, MAX_MONEY)
    if err:
        errors["price_kzt"] = err
    for field in ("place_id", "category_id"):
        raw = (form.get(field) or "").strip()
        values[field] = parse_uuid(raw) if raw else None
        if raw and values[field] is None:
            errors[field] = "Неверный идентификатор"
    values["lat"], values["lon"] = _parse_event_point(form, errors)
    if not values["place_id"] and values["lat"] is None and not ({"place_id", "lat"} & set(errors)):
        errors["place_id"] = "Укажите место или координаты"
    # OPEN(SSOT §16.9): promoted events get the "Реклама / Ad" label; labelling rules not final
    values["is_promoted"] = parse_bool(form.get("is_promoted"))
    return values, errors


def _parse_event_point(form: Mapping[str, str], errors: Errors):
    """Own coordinates of an event: both or none, inside the Almaty area."""
    raw_lat, raw_lon = (form.get("lat") or "").strip(), (form.get("lon") or "").strip()
    if not raw_lat and not raw_lon:
        return None, None
    try:
        lat, lon = float(raw_lat.replace(",", ".")), float(raw_lon.replace(",", "."))
    except ValueError:
        errors["lat"] = "Нужны числа: широта и долгота"
        return None, None
    west, south, east, north = ALMATY_BBOX
    if not (south <= lat <= north and west <= lon <= east):
        errors["lat"] = "Точка вне Алматы"
        return None, None
    return lat, lon


async def check_event_refs(conn, values: Mapping[str, Any], errors: Errors) -> None:
    if values.get("place_id") and "place_id" not in errors:
        place = await fetch_one(conn, sql.PLACE_PUBLIC_FLAG, (values["place_id"],))
        if place is None:
            errors["place_id"] = "Место не найдено"
        elif values.get("is_promoted") and place["is_public"]:
            errors["is_promoted"] = "У достопримечательностей и госмест рекламы быть не может"
    if values.get("category_id") and "category_id" not in errors:
        if not await fetch_one(conn, sql.CATEGORY_EXISTS, (values["category_id"],)):
            errors["category_id"] = "Категория не найдена"


TARIFF_MODES = {
    "walk": "Пешком",
    "scooter": "Самокат",
    "bus": "Автобус",
    "metro": "Метро",
    "taxi": "Такси",
    "car": "Своя машина",
}
TARIFF_FIELDS = {
    "base_kzt": "Фиксированная часть, ₸",
    "per_min_kzt": "За минуту, ₸",
    "per_km_kzt": "За километр, ₸",
}
_TARIFF_MODES_BY_FIELD = {
    "base_kzt": {"scooter", "bus", "metro", "taxi"},
    "per_min_kzt": {"scooter", "taxi"},
    "per_km_kzt": {"taxi", "car"},
}
_TARIFF_AMOUNT_RE = re.compile(r"[0-9]{1,8}(?:\.[0-9]{1,2})?")


def validate_tariff(form: Mapping[str, str]) -> Tuple[Dict[str, Any], Errors]:
    values: Dict[str, Any] = {}
    errors: Errors = {}
    mode = form.get("mode", "")
    values["mode"] = mode
    if mode not in TARIFF_MODES:
        errors["mode"] = "Выберите вид транспорта"
    try:
        values["valid_from"] = date.fromisoformat(form.get("valid_from", ""))
    except ValueError:
        errors["valid_from"] = "Укажите дату начала действия"
    for field in TARIFF_FIELDS:
        raw = form.get(field, "").strip().replace(",", ".")
        if not _TARIFF_AMOUNT_RE.fullmatch(raw):
            errors[field] = "Введите сумму от 0 до 99 999 999,99"
            continue
        amount = Decimal(raw)
        if amount and mode not in _TARIFF_MODES_BY_FIELD[field]:
            errors[field] = "Для этого вида транспорта укажите 0"
        values[field] = amount
    values["approximate"] = parse_bool(form.get("approximate"))
    source, error = clean_text(form.get("source"), 200)
    values["source"] = source
    if not source:
        errors["source"] = error or "Укажите источник или основание оценки"
    return values, errors
