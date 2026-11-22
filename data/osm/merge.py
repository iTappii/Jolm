"""Fold one place row into another without losing curated data. Raw parameterized SQL, no ORM.

Used by the OSM importer (duplicate OSM objects of one venue) and by the curated popular
import (a manual row that turns out to be an OSM object). The surviving row ("keep") gets:
  - dependent rows of the dropped row (hours, photos, menu, curated-route items, events, trip
    items, trip lodging options, user place signals), except where the survivor already has its
    own (hours, menu, same route item, same trip's lodging option);
  - fields the survivor lacks (names, descriptions, address, prices ...);
  - fields the dropped row set by hand (manual_override) when the survivor did not;
  - the union of both manual_override lists.
Then the dropped row is deleted. Column names come from the hard-coded lists below only.
"""

from __future__ import annotations

# nullable columns: the survivor's own value wins, the dropped row only fills holes
FILL_COLUMNS = (
    "name_ru", "name_en", "name_kk", "description_ru", "description_en", "address_ru",
    "address_en", "website", "elevation_m", "setting", "typical_visit_min", "entry_price_kzt",
    "avg_check_kzt", "price_per_night_kzt", "category_id",
)  # fmt: skip
# columns taken from the dropped row when it set them by hand and the survivor did not
TAKEOVER_COLUMNS = FILL_COLUMNS + ("kind", "geom", "is_public", "is_mountain")
_ALL = TAKEOVER_COLUMNS


def _set(column: str) -> str:
    take = (
        f"d.manual_override @> '\"{column}\"'::jsonb "
        f"AND NOT k.manual_override @> '\"{column}\"'::jsonb"
    )
    fallback = f"COALESCE(k.{column}, d.{column})" if column in FILL_COLUMNS else f"k.{column}"
    return f"{column} = CASE WHEN {take} THEN d.{column} ELSE {fallback} END"


MERGE_FIELDS = (
    "UPDATE places k SET\n    "
    + ",\n    ".join(_set(c) for c in _ALL)
    + """,
    is_partner = k.is_partner OR d.is_partner,
    popularity = GREATEST(k.popularity, d.popularity),
    manual_override = (SELECT coalesce(jsonb_agg(DISTINCT v), '[]'::jsonb)
                       FROM jsonb_array_elements(k.manual_override || d.manual_override) AS v),
    data_updated_at = now()
FROM places d
WHERE k.id = %(keep)s AND d.id = %(drop)s
"""
)

MOVE_STATEMENTS = (
    "UPDATE place_hours SET place_id = %(keep)s WHERE place_id = %(drop)s "
    "AND NOT EXISTS (SELECT 1 FROM place_hours WHERE place_id = %(keep)s)",
    "UPDATE place_photos SET place_id = %(keep)s WHERE place_id = %(drop)s",
    "UPDATE place_menu SET place_id = %(keep)s WHERE place_id = %(drop)s "
    "AND NOT EXISTS (SELECT 1 FROM place_menu WHERE place_id = %(keep)s)",
    "UPDATE curated_route_items i SET place_id = %(keep)s WHERE place_id = %(drop)s "
    "AND NOT EXISTS (SELECT 1 FROM curated_route_items j "
    "WHERE j.route_id = i.route_id AND j.place_id = %(keep)s)",
    # events (Ш-48): an event moved onto a public place loses its ad flag (SSOT §12)
    "UPDATE events SET is_promoted = false WHERE place_id = %(drop)s "
    "AND EXISTS (SELECT 1 FROM places WHERE id = %(keep)s AND is_public)",
    "UPDATE events SET place_id = %(keep)s WHERE place_id = %(drop)s",
    # trips (Ш-36): FKs without ON DELETE CASCADE, so every row must move before the delete
    "UPDATE trip_items SET place_id = %(keep)s WHERE place_id = %(drop)s",
    "UPDATE trip_lodging_options SET place_id = %(keep)s WHERE place_id = %(drop)s "
    "AND NOT EXISTS (SELECT 1 FROM trip_lodging_options j "
    "WHERE j.trip_id = trip_lodging_options.trip_id AND j.place_id = %(keep)s)",
    # a trip that lists both places keeps the survivor's row and its recommendation
    "UPDATE trip_lodging_options k SET recommended = true FROM trip_lodging_options d "
    "WHERE d.place_id = %(drop)s AND d.recommended AND k.trip_id = d.trip_id "
    "AND k.place_id = %(keep)s",
    "DELETE FROM trip_lodging_options WHERE place_id = %(drop)s",
    # memory signals of trip edits (Ш-38): FK without ON DELETE CASCADE
    "UPDATE user_place_signals SET place_id = %(keep)s WHERE place_id = %(drop)s",
    # weather change proposals (Ш-40): both place columns, FK without ON DELETE CASCADE
    "UPDATE trip_change_proposals SET place_id = %(keep)s WHERE place_id = %(drop)s",
    "UPDATE trip_change_proposals SET target_place_id = %(keep)s WHERE target_place_id = %(drop)s",
    # favourites (Ш-23b): FK without ON DELETE CASCADE; a user who saved both keeps one row
    "UPDATE user_favorites SET place_id = %(keep)s WHERE place_id = %(drop)s "
    "AND NOT EXISTS (SELECT 1 FROM user_favorites j "
    "WHERE j.user_id = user_favorites.user_id AND j.place_id = %(keep)s)",
    "DELETE FROM user_favorites WHERE place_id = %(drop)s",
    # user submissions (Ш-44): FK without ON DELETE CASCADE; no unique constraint to collide with
    "UPDATE submissions SET place_id = %(keep)s WHERE place_id = %(drop)s",
    # crowd reports (Ш-47): the rows move, the derived profile of the dropped place is rebuilt by
    # the `crowd.aggregate` job, so its rows are just dropped
    "UPDATE place_crowd_reports SET place_id = %(keep)s WHERE place_id = %(drop)s",
    "DELETE FROM place_crowd_profile WHERE place_id = %(drop)s",
    # bookings skeleton (Ш-49): bookings move; a partner that serves both places keeps one link
    # (kinds of the dropped link are added to the survivor's)
    "UPDATE bookings SET place_id = %(keep)s WHERE place_id = %(drop)s",
    "UPDATE partner_places k SET kinds = ARRAY(SELECT DISTINCT unnest(k.kinds || d.kinds)), "
    "external_ref = coalesce(k.external_ref, d.external_ref) "
    "FROM partner_places d WHERE d.place_id = %(drop)s AND k.place_id = %(keep)s "
    "AND k.partner_id = d.partner_id",
    "UPDATE partner_places SET place_id = %(keep)s WHERE place_id = %(drop)s "
    "AND NOT EXISTS (SELECT 1 FROM partner_places j "
    "WHERE j.partner_id = partner_places.partner_id AND j.place_id = %(keep)s)",
    "DELETE FROM partner_places WHERE place_id = %(drop)s",
    # analytics events (Ш-50): FK without ON DELETE CASCADE. The visit views read
    # place_crowd_reports and trip_items, which move above.
    "UPDATE analytics_events SET place_id = %(keep)s WHERE place_id = %(drop)s",
    # live route of a chat (Ш-54): stops and alternatives, FKs without ON DELETE CASCADE. An
    # alternative that would duplicate the stop's place or a sibling alternative is dropped.
    "UPDATE chat_live_stops SET place_id = %(keep)s WHERE place_id = %(drop)s",
    "UPDATE chat_live_alternatives a SET place_id = %(keep)s WHERE a.place_id = %(drop)s "
    "AND NOT EXISTS (SELECT 1 FROM chat_live_alternatives j "
    "WHERE j.chat_id = a.chat_id AND j.ord = a.ord AND j.place_id = %(keep)s)",
    "DELETE FROM chat_live_alternatives WHERE place_id = %(drop)s",
    "DELETE FROM chat_live_alternatives a USING chat_live_stops s "
    "WHERE s.chat_id = a.chat_id AND s.ord = a.ord AND s.place_id = a.place_id",
)

DELETE_DROPPED = "DELETE FROM places WHERE id = %(drop)s AND (%(any_row)s OR osm_id IS NULL)"


def merge_place(conn, keep_id, drop_id, any_row: bool = True) -> None:
    """Merge `drop_id` into `keep_id` and delete it (only a manual row when any_row is False).

    Items of the dropped row that collide with the survivor's are removed by the cascade
    on delete; curated route items that cannot move (route already has the survivor) go too.
    """
    params = {"keep": keep_id, "drop": drop_id, "any_row": any_row}
    conn.execute(MERGE_FIELDS, params)
    for stmt in MOVE_STATEMENTS:
        conn.execute(stmt, params)
    conn.execute(DELETE_DROPPED, params)
