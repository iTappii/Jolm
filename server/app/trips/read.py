"""JSON shapes of the trips read API (Ш-37). Pure functions over rows from `trips.store`.

Times are returned in Asia/Almaty (offset +05:00 since 2024), `day` / `date` are local calendar
dates. Money is integer tenge for one traveller. Names follow Accept-Language (ru: ru, en, kk;
en: en, ru, kk).
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.places import service
from app.routing.service import ALMATY_TZ


def local(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(ALMATY_TZ).isoformat() if value else None


def place_ref(row: Dict[str, Any], locale: str) -> Dict[str, Any]:
    """Short place reference; `row` has name_ru, name_en, category, lat, lon and `place_id`."""
    name, lang = service.pick_text(row, "name", locale)
    return {
        "id": str(row["place_id"]),
        "name": name or "",
        "name_lang": lang,
        "category": row["category"],
        "lat": row["lat"],
        "lon": row["lon"],
    }


def place_summary(row: Dict[str, Any], locale: str) -> Dict[str, Any]:
    out = place_ref(row, locale)
    out["category_name"] = row["category_name_ru" if locale == "ru" else "category_name_en"]
    out["photo"] = (
        {"id": str(row["photo_id"]), "storage_key": row["photo_key"]} if row["photo_id"] else None
    )
    return out


def item_json(row: Dict[str, Any], locale: str) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "ord": row["ord"],
        "kind": row["kind"],
        "meal": row["meal"],
        "place": place_summary(row, locale),
        "starts_at": local(row["starts_at"]),
        "ends_at": local(row["ends_at"]),
        "visit_min": row["visit_min"],
        "must_have": row["is_must_have"],
        "est_cost_kzt": row["est_cost_kzt"],
        "cost_assumed": row["cost_assumed"],
        "hours_assumed": row["hours_assumed"],
        "rain_exposed": row["rain_exposed"],
    }


def leg_json(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "from_item_id": str(row["from_item_id"]) if row["from_item_id"] else None,
        "to_item_id": str(row["to_item_id"]),
        "depart_at": local(row["depart_at"]),
        "travel_s": row["travel_s"],
        "estimated": row["estimated"],
        "chosen_mode": row["chosen_mode"],
        "cost_kzt": row["cost_kzt"],
        "options": row["options"],
    }


def trip_dates(start: date, end: date) -> List[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def days_json(
    trip: Dict[str, Any], items: List[Dict[str, Any]], legs: List[Dict[str, Any]], locale: str
) -> List[Dict[str, Any]]:
    """Every day of the trip, empty ones included: `{date, items: [...], legs: [...]}`."""
    by_day: Dict[date, Dict[str, List[Dict[str, Any]]]] = {
        d: {"items": [], "legs": []} for d in trip_dates(trip["start_date"], trip["end_date"])
    }
    for row in items:
        by_day.setdefault(row["day"], {"items": [], "legs": []})["items"].append(
            item_json(row, locale)
        )
    for row in legs:
        by_day.setdefault(row["day"], {"items": [], "legs": []})["legs"].append(leg_json(row))
    return [
        {"date": d.isoformat(), "items": v["items"], "legs": v["legs"]}
        for d, v in sorted(by_day.items())
    ]


def lodging_option_json(row: Dict[str, Any], locale: str) -> Dict[str, Any]:
    out = place_ref(row, locale)
    out.update(
        rank=row["rank"],
        price_per_night_kzt=row["price_per_night_kzt"],
        price_assumed=row["price_assumed"],
        nights=row["nights"],
        total_kzt=row["total_kzt"],
        recommended=row["recommended"],
    )
    return out


def _pair_swaps(removed: List[Dict[str, Any]], added: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pair places that left the plan with the ones that came in: same kind and meal slot,
    the nearest day first. Derived from the stored variant rows (the budget block stores no
    place ids); a place without a partner has `"to": null`."""
    left = list(added)
    pairs = []
    for old in removed:
        fits = [new for new in left if new["kind"] == old["kind"] and new["meal"] == old["meal"]]
        new = min(fits, key=lambda n: (abs((n["day"] - old["day"]).days), n["ord"]), default=None)
        if new is not None:
            left.remove(new)
        pairs.append((old, new))
    return [{"from": o, "to": n} for o, n in pairs]


def variants_json(
    stored: Optional[Dict[str, Any]],
    main: List[Dict[str, Any]],
    variant_rows: Dict[str, List[Dict[str, Any]]],
    lodging: List[Dict[str, Any]],
    locale: str,
) -> Optional[Dict[str, Any]]:
    """The stored variant numbers plus the places that differ from the plan, so the client can
    show the choice: `drop_places.removed`, `cheaper.swaps` and `cheaper.lodging`."""
    if not stored:
        return None
    main_places = {r["place_id"] for r in main}
    out: Dict[str, Any] = {}
    for kind, numbers in stored.items():
        rows = variant_rows.get(kind, [])
        variant_places = {r["place_id"] for r in rows}
        gone = [r for r in main if r["place_id"] not in variant_places]
        came = [r for r in rows if r["place_id"] not in main_places]
        entry = dict(numbers)
        if kind == "drop_places":
            entry["removed"] = [place_ref(r, locale) for r in gone]
        else:
            entry["swaps"] = [
                {
                    "from": place_ref(pair["from"], locale),
                    "to": place_ref(pair["to"], locale) if pair["to"] else None,
                }
                for pair in _pair_swaps(gone, came)
            ]
            cheapest = min(lodging, key=lambda o: (o["total_kzt"], o["rank"]), default=None)
            entry["lodging"] = (
                dict(place_ref(cheapest, locale), total_kzt=cheapest["total_kzt"])
                if numbers.get("lodging_changed") and cheapest
                else None
            )
        out[kind] = entry
    return out


def budget_json(
    trip: Dict[str, Any],
    main: List[Dict[str, Any]],
    variant_rows: Dict[str, List[Dict[str, Any]]],
    lodging: List[Dict[str, Any]],
    locale: str,
) -> Dict[str, Any]:
    stored = trip["budget"]
    out = dict(stored)
    block = dict(stored.get("lodging") or {})
    block["options"] = [lodging_option_json(o, locale) for o in lodging]
    out["lodging"] = block
    out["variants"] = variants_json(stored.get("variants"), main, variant_rows, lodging, locale)
    return out


def trip_json(
    trip: Dict[str, Any],
    items: List[Dict[str, Any]],
    legs: List[Dict[str, Any]],
    variant_rows: Dict[str, List[Dict[str, Any]]],
    lodging: List[Dict[str, Any]],
    locale: str,
) -> Dict[str, Any]:
    return {
        "id": str(trip["id"]),
        "chat_id": str(trip["chat_id"]) if trip["chat_id"] else None,
        "version": trip["version"],
        "status": trip["status"],
        "start_date": trip["start_date"].isoformat(),
        "end_date": trip["end_date"].isoformat(),
        "budget_kzt": trip["budget_kzt"],
        "total_cost_kzt": trip["total_cost_kzt"],
        "budget_choice": trip["budget_choice"],
        "weather_checked_at": local(trip["weather_checked_at"]),
        "created_at": local(trip["created_at"]),
        "updated_at": local(trip["updated_at"]),
        "days": days_json(trip, items, legs, locale),
        "budget": budget_json(trip, items, variant_rows, lodging, locale),
        "warnings": trip["warnings"],
        "must_have_unmet": trip["must_have_unmet"],
    }


def summary_json(row: Dict[str, Any]) -> Dict[str, Any]:
    budget = row["budget"] or {}
    return {
        "id": str(row["id"]),
        "chat_id": str(row["chat_id"]) if row["chat_id"] else None,
        "start_date": row["start_date"].isoformat(),
        "end_date": row["end_date"].isoformat(),
        "days": (row["end_date"] - row["start_date"]).days + 1,
        "version": row["version"],
        "status": row["status"],
        "budget": {
            "status": budget.get("status"),
            "budget_kzt": row["budget_kzt"],
            "total_kzt": row["total_cost_kzt"],
        },
        "updated_at": local(row["updated_at"]),
    }
