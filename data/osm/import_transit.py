"""Import Almaty public transport from OpenStreetMap into transit_* tables (TECH_PLAN Ш-21).

Usage:
    python data/osm/import_transit.py [--pbf PATH] [--seed PATH] [--manual-stops PATH] [--dry-run]

Source: data/osm/cache/kazakhstan.osm.pbf (`make osm-pbf`), route relations with
route=subway|bus|trolleybus|tram inside the Almaty bbox. One relation = one direction (or a loop);
its ordered stop members (roles stop/platform and variants) become transit_route_stops.
Headways/speeds: data/seed/transit_manual.csv (approximate, see that file); a route with no
specific seed row takes OSM `interval` if tagged, else the kind default.

Assumptions (documented, not hidden):
  * OSM member order of stops is the travel order. Mis-ordered relations give wrong rides; the
    community can fix them in OSM, or by hand through manual_override.
  * Relations whose member order is not travel order (zigzag ratio, see zigzag_ratio) are re-sorted
    along the chained way geometry; if still implausible they are dropped (reported).
  * Stops are node members only; platform *ways* are skipped (counted in the report).
  * Per relation, if both stop_position and platform members exist, the class with more members is
    the sequence and the other class is folded into it (same station, <=80 m, compatible name).
    Metro stations of opposite directions (different nodes, same name, <=200 m) become one stop.
    Bus stops on opposite sides of a road stay separate stops (directions differ).
  * A relation with fewer than 2 stops inside the bbox is skipped; stops outside the bbox are
    dropped, so a route leaving the city is cut at the bbox edge.
  * Re-import is idempotent; fields named in manual_override are kept. OSM routes that vanished
    from the extract (and carry no manual edits) are deleted, together with their orphan stops.

Attribution: map data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from import_places import BBOX, database_url, find_pbf, in_bbox  # noqa: E402

ROUTE_KINDS = {"subway": "metro", "bus": "bus", "trolleybus": "trolleybus", "tram": "tram"}
KIND_PRIORITY = ["metro", "tram", "trolleybus", "bus"]
DEFAULT_SEED = HERE.parent / "seed" / "transit_manual.csv"
DEFAULT_MANUAL_STOPS = HERE.parent / "seed" / "transit_manual_stops.csv"
FOLD_RADIUS_M = 80.0
METRO_MERGE_RADIUS_M = 200.0
KAZAKH_LETTERS = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")

NODE_TAG_KEYS = ("name", "name:ru", "name:en", "name:kk", "public_transport", "highway", "railway")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def norm_name(name: Optional[str]) -> str:
    return re.sub(r"[^\w]+", "", (name or "").lower())


def stop_role_class(role: str, tags: Optional[dict]) -> Optional[str]:
    """'stop' | 'platform' | None for a node member of a route relation."""
    r = role.lower()
    if "platform" in r:
        return "platform"
    if "stop" in r or r == "station":
        return "stop"
    if r == "" and tags:
        if tags.get("highway") == "bus_stop" or tags.get("public_transport") == "platform":
            return "platform"
        if tags.get("public_transport") in ("stop_position", "station") or tags.get("railway") in (
            "stop",
            "station",
        ):
            return "stop"
    return None


def localized_names(tags: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    name, kk = tags.get("name"), tags.get("name:kk")
    ru = tags.get("name:ru")
    if ru is None and name and name != kk and not (set(name) & KAZAKH_LETTERS):
        ru = name
    if kk is None and name and (set(name) & KAZAKH_LETTERS):
        kk = name
    return ru, tags.get("name:en"), kk


# --- extraction (pyosmium) ------------------------------------------------------------------


def extract(path: str):
    """Return (relations, nodes, ways).

    relations: id -> {kind, tags, members[(type, ref, role)]}; ways: id -> node ids.
    """
    import osmium

    relations: Dict[int, dict] = {}
    for rel in osmium.FileProcessor(str(path), osmium.osm.RELATION):
        t = rel.tags
        if t.get("type") != "route" or t.get("route") not in ROUTE_KINDS:
            continue
        relations[rel.id] = {
            "kind": ROUTE_KINDS[t["route"]],
            "tags": {
                k: t.get(k) for k in ("ref", "name", "name:ru", "name:en", "name:kk", "interval")
            },
            "members": [(m.type, m.ref, m.role) for m in rel.members],
        }
    needed = {ref for r in relations.values() for ty, ref, _ in r["members"] if ty == "n"}
    way_ids = {ref for r in relations.values() for ty, ref, _ in r["members"] if ty == "w"}
    ways: Dict[int, List[int]] = {}
    for w in osmium.FileProcessor(str(path), osmium.osm.WAY):
        if w.id in way_ids:
            ways[w.id] = [n.ref for n in w.nodes]
    needed_all = needed | {n for refs in ways.values() for n in refs}
    nodes: Dict[int, dict] = {}
    for n in osmium.FileProcessor(str(path), osmium.osm.NODE):
        if n.id in needed_all and n.location.valid():
            nodes[n.id] = {
                "lon": n.location.lon,
                "lat": n.location.lat,
                "tags": {k: n.tags.get(k) for k in NODE_TAG_KEYS if n.tags.get(k) is not None}
                if n.id in needed
                else {},
            }
    return relations, nodes, ways


# --- pure transformation ----------------------------------------------------------------------


def relation_sequence(rel: dict, nodes: dict, bbox, stats: Counter):
    """Ordered node ids of a relation (one class) + alias map {folded_node: node}."""
    members = []
    for ty, ref, role in rel["members"]:
        if ty == "w" and ("stop" in role.lower() or "platform" in role.lower()):
            stats["way_stop_members_skipped"] += 1
            continue
        if ty != "n" or ref not in nodes:
            continue
        n = nodes[ref]
        cls = stop_role_class(role, n["tags"])
        if cls is None or not in_bbox(n["lon"], n["lat"], bbox):
            continue
        members.append((ref, cls))
    n_plat = sum(1 for _, c in members if c == "platform")
    main = "platform" if n_plat >= len(members) - n_plat else "stop"
    seq = [ref for ref, c in members if c == main]
    aliases: Dict[int, int] = {}
    for ref, c in members:
        if c == main:
            continue
        n = nodes[ref]
        best, best_d = None, FOLD_RADIUS_M
        for cand in seq:
            m = nodes[cand]
            a, b = norm_name(n["tags"].get("name")), norm_name(m["tags"].get("name"))
            if a and b and a != b:
                continue
            d = haversine_m(n["lat"], n["lon"], m["lat"], m["lon"])
            if d <= best_d:
                best, best_d = cand, d
        if best is not None and best != ref:
            aliases[ref] = best
            stats["stop_platform_folded"] += 1
        else:
            stats["unmatched_other_class_dropped"] += 1
    return seq, aliases


MAX_ZIGZAG = 1.5  # path length / greedy shortest path above this: member order is not travel order
DROP_ZIGZAG = 2.2  # still above this after repair: the route is dropped


def zigzag_ratio(seq: List[int], nodes: dict) -> float:
    """Length of the stop sequence / length of a greedy nearest-neighbour path from its first stop.

    ~1.0-1.3 for a properly ordered line; far above 1.5 for relations whose members are unordered
    (round-trip relations with both directions mixed, hand-edited member lists).
    """
    pts = [(nodes[n]["lat"], nodes[n]["lon"]) for n in seq]
    length = sum(haversine_m(*a, *b) for a, b in zip(pts, pts[1:]))
    rest, cur, greedy = pts[1:], pts[0], 0.0
    while rest:
        j = min(range(len(rest)), key=lambda i: haversine_m(*cur, *rest[i]))
        greedy += haversine_m(*cur, *rest[j])
        cur = rest.pop(j)
    return length / max(greedy, 1.0)


def route_polyline(rel: dict, nodes: dict, ways: dict) -> List[Tuple[float, float]]:
    """Chain the relation's way members into one (lat, lon) polyline (best effort, gaps allowed)."""
    chain: List[int] = []
    for ty, ref, _ in rel["members"]:
        refs = [n for n in ways.get(ref, []) if n in nodes] if ty == "w" else []
        if len(refs) < 2:
            continue
        if not chain:
            chain = list(refs)
            continue
        ends = {"cs": chain[0], "ce": chain[-1]}
        if refs[0] == ends["ce"]:
            chain += refs[1:]
        elif refs[-1] == ends["ce"]:
            chain += refs[-2::-1]
        elif refs[-1] == ends["cs"]:
            chain = refs[:-1] + chain
        elif refs[0] == ends["cs"]:
            chain = refs[:0:-1] + chain
        else:  # gap: attach at the nearer end of the new way

            def d(n, m):
                return haversine_m(
                    nodes[n]["lat"], nodes[n]["lon"], nodes[m]["lat"], nodes[m]["lon"]
                )

            chain += refs if d(chain[-1], refs[0]) <= d(chain[-1], refs[-1]) else refs[::-1]
    return [(nodes[n]["lat"], nodes[n]["lon"]) for n in chain]


def reorder_by_polyline(seq: List[int], nodes: dict, poly: List[Tuple[float, float]]) -> List[int]:
    """Sort stops by the chainage of their nearest polyline vertex (stable)."""
    if len(poly) < 2:
        return seq
    cum = [0.0]
    for a, b in zip(poly, poly[1:]):
        cum.append(cum[-1] + haversine_m(*a, *b))

    def chainage(n: int) -> float:
        p = (nodes[n]["lat"], nodes[n]["lon"])
        i = min(range(len(poly)), key=lambda k: haversine_m(*p, *poly[k]))
        return cum[i]

    keyed = [(chainage(n), i, n) for i, n in enumerate(seq)]
    return [n for _, _, n in sorted(keyed)]


def build_network(relations: dict, nodes: dict, ways: Optional[dict] = None, bbox=BBOX):
    """-> (stops, routes, stats). stops: node_id -> dict; routes: dicts with 'stop_nodes'."""
    stats: Counter = Counter()
    stats["relations_total"] = len(relations)
    alias: Dict[int, int] = {}
    raw_routes = []
    for rid, rel in sorted(relations.items()):
        seq, al = relation_sequence(rel, nodes, bbox, stats)
        if not seq:
            stats["relations_outside_bbox_or_no_stops"] += 1
            continue
        if len(seq) < 2:
            stats["routes_skipped_lt2_stops"] += 1
            continue
        if rel["kind"] != "metro":
            ratio = zigzag_ratio(seq, nodes)
            if ratio > MAX_ZIGZAG and ways:
                fixed = reorder_by_polyline(seq, nodes, route_polyline(rel, nodes, ways))
                new_ratio = zigzag_ratio(fixed, nodes)
                if new_ratio < ratio:
                    seq, ratio = fixed, new_ratio
                    stats["routes_reordered_by_geometry"] += 1
            if ratio > DROP_ZIGZAG:
                stats["routes_dropped_unordered"] += 1
                continue
        for k, v in al.items():
            alias.setdefault(k, v)
        raw_routes.append((rid, rel, seq))

    # metro: one station per name (opposite directions use different nodes)
    metro_nodes = sorted({n for _, rel, seq in raw_routes if rel["kind"] == "metro" for n in seq})
    reps: List[int] = []
    for n in metro_nodes:
        nn = nodes[n]
        key = norm_name(nn["tags"].get("name"))
        for r in reps:
            rr = nodes[r]
            if (
                key
                and key == norm_name(rr["tags"].get("name"))
                and haversine_m(nn["lat"], nn["lon"], rr["lat"], rr["lon"]) <= METRO_MERGE_RADIUS_M
            ):
                alias.setdefault(n, r)
                stats["metro_directions_merged"] += 1
                break
        else:
            reps.append(n)

    def resolve(n: int) -> int:
        for _ in range(4):
            if n in alias and alias[n] != n:
                n = alias[n]
            else:
                break
        return n

    routes = []
    stop_kinds: Dict[int, set] = {}
    for rid, rel, seq in raw_routes:
        out: List[int] = []
        for n in seq:
            n = resolve(n)
            if not out or out[-1] != n:
                out.append(n)
        if len(out) < 2:
            stats["routes_skipped_lt2_stops"] += 1
            continue
        for n in out:
            stop_kinds.setdefault(n, set()).add(rel["kind"])
        routes.append(
            {"relation_id": rid, "kind": rel["kind"], "tags": rel["tags"], "stop_nodes": out}
        )
        stats["routes_" + rel["kind"]] += 1

    twins: Dict[int, List[int]] = {}
    for k in alias:
        twins.setdefault(resolve(k), []).append(k)
    stops: Dict[int, dict] = {}
    for n, kinds in stop_kinds.items():
        nn = nodes[n]
        tags = dict(nn["tags"])
        if not tags.get("name"):  # borrow a name from a folded twin
            for k in twins.get(n, []):
                if nodes.get(k, {}).get("tags", {}).get("name"):
                    tags = dict(nodes[k]["tags"])
                    break
        ru, en, kk = localized_names(tags)
        stops[n] = {
            "osm_id": n,
            "lat": nn["lat"],
            "lon": nn["lon"],
            "name_ru": ru,
            "name_en": en,
            "name_kk": kk,
            "kind": next(k for k in KIND_PRIORITY if k in kinds),
        }
        if not (ru or en or kk):
            stats["stops_unnamed"] += 1
    return stops, routes, stats


def parse_interval(value: Optional[str]) -> Optional[float]:
    """OSM `interval` tag (minutes, or HH:MM[:SS]) -> minutes, only if plausible (1..120)."""
    if not value:
        return None
    v = value.strip()
    try:
        minutes = float(v)
    except ValueError:
        m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", v)
        if not m:
            return None
        minutes = int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3) or 0) / 60
    return minutes if 1 <= minutes <= 120 else None


def load_seed(path: Path) -> Dict[Tuple[str, str], dict]:
    with open(path, encoding="utf-8", newline="") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    seed: Dict[Tuple[str, str], dict] = {}
    for row in csv.DictReader(lines):
        kind = row["kind"].strip()
        if kind not in KIND_PRIORITY:
            raise SystemExit(f"bad kind in seed: {kind!r}")
        seed[(kind, (row["ref"] or "").strip())] = {
            "avg_headway_min": float(row["avg_headway_min"]),
            "speed_kmh": float(row["speed_kmh"]),
            "fare_kzt": int(row["fare_kzt"]) if row.get("fare_kzt") else None,
        }
    for kind in KIND_PRIORITY:
        if (kind, "") not in seed:
            raise SystemExit(f"seed has no default row for kind {kind!r}")
    return seed


def seed_for(seed: dict, kind: str, ref: Optional[str]) -> dict:
    return seed.get((kind, ref or "")) or seed[(kind, "")]


def apply_manual_stops(stops: dict, routes: list, path: Path) -> Counter:
    """Splice seed stops at explicit OSM anchors on verified route relations."""
    stats: Counter = Counter()
    by_relation = {route["relation_id"]: route for route in routes}
    replaced_nodes = set()
    with path.open(encoding="utf-8", newline="") as seed_file:
        rows = csv.DictReader(line for line in seed_file if not line.startswith("#"))
        for row in rows:
            route = by_relation.get(int(row["relation_id"]))
            stop_id = UUID(row["stop_id"])
            anchor = int(row["anchor_node"])
            if not route or route["kind"] != row["kind"] or route["tags"].get("ref") != row["ref"]:
                stats["manual_stop_links_skipped"] += 1
                continue
            sequence = route["stop_nodes"]
            if stop_id in sequence:
                continue
            if sequence.count(anchor) != 1:
                stats["manual_stop_links_skipped"] += 1
                continue
            stop = {
                "id": stop_id,
                "kind": row["kind"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                **{key: row[key] or None for key in ("name_ru", "name_en", "name_kk")},
            }
            if not in_bbox(stop["lon"], stop["lat"]):
                raise ValueError(f"manual stop {stop_id} outside import region")
            if stops.setdefault(stop_id, stop) != stop:
                raise ValueError(f"inconsistent seed coordinates or labels for stop {stop_id}")
            index = sequence.index(anchor)
            placement = row["placement"]
            if placement == "replace":
                sequence[index] = stop_id
                replaced_nodes.add(anchor)
            elif placement == "before":
                sequence.insert(index, stop_id)
            else:
                raise ValueError(f"unknown manual stop placement: {placement!r}")
            stats["manual_stop_links"] += 1
    if replaced_nodes:
        referenced = {node for route in routes for node in route["stop_nodes"]}
        for node in replaced_nodes - referenced:
            stops.pop(node, None)
    return stats


# --- database (raw parameterized SQL, no ORM) -------------------------------------------------

STOP_VALUES = """%(kind)s, %(name_ru)s, %(name_en)s, %(name_kk)s,
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography"""

UPDATE_STOP = """
DO UPDATE SET
    kind    = CASE WHEN transit_stops.manual_override @> '"kind"'::jsonb
                   THEN transit_stops.kind ELSE EXCLUDED.kind END,
    name_ru = CASE WHEN transit_stops.manual_override @> '"name_ru"'::jsonb
                   THEN transit_stops.name_ru ELSE EXCLUDED.name_ru END,
    name_en = CASE WHEN transit_stops.manual_override @> '"name_en"'::jsonb
                   THEN transit_stops.name_en ELSE EXCLUDED.name_en END,
    name_kk = CASE WHEN transit_stops.manual_override @> '"name_kk"'::jsonb
                   THEN transit_stops.name_kk ELSE EXCLUDED.name_kk END,
    geom    = CASE WHEN transit_stops.manual_override @> '"geom"'::jsonb
                   THEN transit_stops.geom ELSE EXCLUDED.geom END,
    updated_at = now()
RETURNING id, (xmax = 0) AS inserted
"""

UPSERT_STOP = f"""
INSERT INTO transit_stops (osm_type, osm_id, kind, name_ru, name_en, name_kk, geom)
VALUES ('node', %(osm_id)s, {STOP_VALUES})
ON CONFLICT (osm_type, osm_id) {UPDATE_STOP}
"""

UPSERT_MANUAL_STOP = f"""
INSERT INTO transit_stops (id, kind, name_ru, name_en, name_kk, geom)
VALUES (%(id)s, {STOP_VALUES})
ON CONFLICT (id) {UPDATE_STOP}
"""

UPSERT_ROUTE = """
INSERT INTO transit_routes (osm_relation_id, kind, ref, name_ru, name_en,
                            avg_headway_min, speed_kmh)
VALUES (%(relation_id)s, %(kind)s, %(ref)s, %(name_ru)s, %(name_en)s, %(headway)s, %(speed)s)
ON CONFLICT (osm_relation_id) DO UPDATE SET
    kind     = CASE WHEN transit_routes.manual_override @> '"kind"'::jsonb
                    THEN transit_routes.kind ELSE EXCLUDED.kind END,
    ref      = CASE WHEN transit_routes.manual_override @> '"ref"'::jsonb
                    THEN transit_routes.ref ELSE EXCLUDED.ref END,
    name_ru  = CASE WHEN transit_routes.manual_override @> '"name_ru"'::jsonb
                    THEN transit_routes.name_ru ELSE EXCLUDED.name_ru END,
    name_en  = CASE WHEN transit_routes.manual_override @> '"name_en"'::jsonb
                    THEN transit_routes.name_en ELSE EXCLUDED.name_en END,
    avg_headway_min = CASE WHEN transit_routes.manual_override @> '"avg_headway_min"'::jsonb
                    THEN transit_routes.avg_headway_min ELSE EXCLUDED.avg_headway_min END,
    speed_kmh = CASE WHEN transit_routes.manual_override @> '"speed_kmh"'::jsonb
                    THEN transit_routes.speed_kmh ELSE EXCLUDED.speed_kmh END,
    updated_at = now()
RETURNING id, (xmax = 0) AS inserted, manual_override
"""

DELETE_ROUTE_STOPS = "DELETE FROM transit_route_stops WHERE route_id = %s"
INSERT_ROUTE_STOP = "INSERT INTO transit_route_stops (route_id, stop_id, ord) VALUES (%s, %s, %s)"
DELETE_STALE_ROUTES = """
DELETE FROM transit_routes
WHERE osm_relation_id IS NOT NULL AND NOT (osm_relation_id = ANY(%s))
  AND manual_override = '[]'::jsonb
"""
DELETE_ORPHAN_STOPS = """
DELETE FROM transit_stops s
WHERE s.osm_id IS NOT NULL AND s.manual_override = '[]'::jsonb
  AND NOT EXISTS (SELECT 1 FROM transit_route_stops rs WHERE rs.stop_id = s.id)
"""


def write_db(conn, stops: dict, routes: list, seed: dict) -> Counter:
    """Idempotent upsert inside the caller's transaction. Returns counters."""
    c: Counter = Counter()
    ids: Dict[int | UUID, object] = {}
    for n, s in stops.items():
        row = conn.execute(UPSERT_MANUAL_STOP if isinstance(n, UUID) else UPSERT_STOP, s).fetchone()
        ids[n] = row[0]
        c["stops_inserted" if row[1] else "stops_updated"] += 1
    for r in routes:
        t = r["tags"]
        ref = (t.get("ref") or "").strip() or None
        name_ru, name_en, _ = localized_names(t)
        params = dict(seed_for(seed, r["kind"], ref))
        if (r["kind"], ref or "") not in seed:  # no route-specific seed row: trust OSM `interval`
            interval = parse_interval(t.get("interval"))
            if interval:
                params["avg_headway_min"] = interval
        row = conn.execute(
            UPSERT_ROUTE,
            {
                "relation_id": r["relation_id"],
                "kind": r["kind"],
                "ref": ref,
                "name_ru": name_ru,
                "name_en": name_en,
                "headway": params["avg_headway_min"],
                "speed": params["speed_kmh"],
            },
        ).fetchone()
        c["routes_inserted" if row[1] else "routes_updated"] += 1
        if "stops" in row[2]:
            continue
        conn.execute(DELETE_ROUTE_STOPS, (row[0],))
        for i, n in enumerate(r["stop_nodes"]):
            conn.execute(INSERT_ROUTE_STOP, (row[0], ids[n], i))
    if routes:  # never wipe the network because of an empty/broken extract
        keep = [r["relation_id"] for r in routes]
        c["routes_deleted_stale"] = conn.execute(DELETE_STALE_ROUTES, (keep,)).rowcount
        c["stops_deleted_orphan"] = conn.execute(DELETE_ORPHAN_STOPS).rowcount
    return c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pbf", help="path to kazakhstan .osm.pbf")
    ap.add_argument("--seed", default=str(DEFAULT_SEED))
    ap.add_argument("--manual-stops", type=Path, default=DEFAULT_MANUAL_STOPS)
    ap.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    args = ap.parse_args(argv)

    seed = load_seed(Path(args.seed))
    pbf = find_pbf(args.pbf)
    print(f"reading {pbf} (bbox {BBOX})", flush=True)
    relations, nodes, ways = extract(str(pbf))
    stops, routes, stats = build_network(relations, nodes, ways)
    stats.update(apply_manual_stops(stops, routes, args.manual_stops))
    if not args.dry_run:
        import psycopg

        with psycopg.connect(database_url()) as conn:
            with conn.transaction():
                stats.update(write_db(conn, stops, routes, seed))
    print(
        f"routes imported: {len(routes)}  stops: {len(stops)}"
        + ("  (dry run)" if args.dry_run else "")
    )
    for k in sorted(stats):
        print(f"  {k}: {stats[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
