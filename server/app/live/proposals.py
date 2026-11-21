"""Weather change proposals (Ш-40): create (worker), list / accept / decline (API).

Accepting applies the change through the Ш-38 edit machinery (`edit.move_item`,
`edit.replace_item`) in the caller's transaction with the trip locked, and bumps the trip
version. A proposal made for an older version is stale: it becomes 'expired' and accept answers
409 `proposal_stale` (the caller persists the expiry before raising, see `accept`).
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from app import worker
from app.db import fetch_all
from app.errors import AppError
from app.live import messages
from app.live import store as live_store
from app.live.engine import Spec
from app.planner import sql as planner_sql
from app.planner.build import place_name
from app.planner.model import place_from_row
from app.trips import edit, read, store

log = logging.getLogger("app.live")


async def create(conn, trip: dict, spec: Spec, locale: str, chat_id: Optional[UUID]) -> UUID:
    """Store the proposal, tell the person in the trip's chat and queue a push. One transaction."""
    problem = spec.problem
    diff = {"problem": {"type": problem.kind, "hours": list(problem.hours), "peak": problem.peak}}
    proposal_id = await live_store.insert_proposal(
        conn,
        {
            "user_id": trip["user_id"],
            "trip_id": trip["id"],
            "kind": spec.kind,
            "trip_version": trip["version"],
            "day": spec.day,
            "to_day": spec.to_day,
            "item_id": spec.item["id"],
            "place_id": spec.place.id,
            "target_place_id": spec.target.id if spec.target else None,
            "diff": diff,
        },
    )
    texts = messages.proposal_texts(
        locale, spec.kind, problem, spec.day, place_name(spec.place, locale),
        to_day=spec.to_day, target=place_name(spec.target, locale) if spec.target else None,
    )  # fmt: skip
    if chat_id is not None:
        await live_store.add_chat_message(
            conn, chat_id, texts["message"], "system.weather.v1", proposal_id
        )
    note = await live_store.add_notification(
        conn, trip["user_id"], "weather_proposal", texts["title"], texts["body"],
        {
            "type": "weather_proposal",
            "trip_id": str(trip["id"]),
            "proposal_id": str(proposal_id),
            "chat_id": str(chat_id) if chat_id else None,
        },
        "proposal:%s" % proposal_id,
    )  # fmt: skip
    if note is not None:
        await worker.enqueue(conn, "push.send", {"notification_id": str(note)})
    return proposal_id


async def _place_refs(conn, ids: list, locale: str) -> Dict[UUID, Dict[str, Any]]:
    if not ids:
        return {}
    rows = await fetch_all(conn, planner_sql.PLACES_BY_ID, {"ids": ids})
    out = {}
    for r in rows:
        place = place_from_row(r)
        out[place.id] = {
            "id": str(place.id),
            "name": place_name(place, locale),
            "category": place.category,
            "lat": place.lat,
            "lon": place.lon,
        }
    return out


async def list_json(conn, trip: dict, locale: str) -> Dict[str, Any]:
    rows = await live_store.proposals_of_trip(conn, trip["id"])
    ids = list(
        {r["place_id"] for r in rows} | {r["target_place_id"] for r in rows if r["target_place_id"]}
    )
    refs = await _place_refs(conn, ids, locale)
    items = []
    for r in rows:
        status = r["status"]
        if status == "pending" and r["trip_version"] != trip["version"]:
            status = "expired"  # stale: the plan changed since
        items.append(
            {
                "id": str(r["id"]),
                "trip_id": str(r["trip_id"]),
                "reason": r["reason"],
                "kind": r["kind"],
                "status": status,
                "trip_version": r["trip_version"],
                "day": r["day"].isoformat(),
                "to_day": r["to_day"].isoformat() if r["to_day"] else None,
                "item_id": str(r["item_id"]) if r["item_id"] else None,
                "problem": (r["diff"] or {}).get("problem"),
                "place": refs.get(r["place_id"]),
                "target_place": refs.get(r["target_place_id"]) if r["target_place_id"] else None,
                "created_at": read.local(r["created_at"]),
                "decided_at": read.local(r["decided_at"]),
            }
        )
    return {"items": items}


# OPEN(SSOT §16.4): weather changes are applied only after the person accepts (TECH_PLAN §2).
async def accept(
    conn,
    router: Any,
    user_id: UUID,
    proposal_id: UUID,
    locale: str,
    forecast: Any = None,
) -> Optional[Dict[str, Any]]:
    """Apply the proposal. Returns the edit result, or None when it is stale: the proposal was
    marked expired and the CALLER raises 409 `proposal_stale` after committing that mark."""
    proposal = await live_store.proposal_for_update(conn, user_id, proposal_id)
    if proposal is None:
        raise AppError(404, "not_found")
    if proposal["status"] != "pending":
        raise AppError(409, "proposal_decided")
    trip = await store.get_trip_row(conn, user_id, proposal["trip_id"], lock=True)
    if trip["version"] != proposal["trip_version"]:
        await live_store.expire(conn, [proposal_id])
        return None
    items = await store.main_items(conn, trip["id"])
    item = next((r for r in items if r["id"] == proposal["item_id"]), None)
    if item is None or item["place_id"] != proposal["place_id"] or item["day"] != proposal["day"]:
        await live_store.expire(conn, [proposal_id])
        return None
    if proposal["kind"] == "move_day":
        result = await edit.move_item(
            conn, router, user_id, trip["id"], item["id"], proposal["to_day"], locale, forecast
        )
    else:
        result = await edit.replace_item(
            conn, router, user_id, trip["id"], item["id"], locale,
            place_id=proposal["target_place_id"], force=True, forecast=forecast,
            record_signal=False,
        )  # fmt: skip
    await live_store.set_status(conn, proposal_id, "accepted")
    await live_store.expire_stale(conn, trip["id"], result["version"])
    # the plan changed: look at the next suffering stop soon (one proposal at a time)
    await worker.enqueue(
        conn, "weather.recheck", {"trip_id": str(trip["id"]), "force": True},
        dedupe_key="weather.recheck:%s:v%s" % (trip["id"], result["version"]),
    )  # fmt: skip
    result["proposal"] = {"id": str(proposal_id), "status": "accepted"}
    return result


async def decline(conn, user_id: UUID, proposal_id: UUID) -> Dict[str, Any]:
    proposal = await live_store.proposal_for_update(conn, user_id, proposal_id)
    if proposal is None:
        raise AppError(404, "not_found")
    if proposal["status"] != "pending":
        raise AppError(409, "proposal_decided")
    await live_store.set_status(conn, proposal_id, "declined")
    return {"id": str(proposal_id), "status": "declined"}
