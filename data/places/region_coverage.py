"""Coverage report of a region: how many places, how complete, from which sources (Ш-58).

Usage:
    python data/places/region_coverage.py --region kazakhstan [--out docs/reviews/Ш-58-coverage.md]

Counts the places whose point lies inside the region boundary (hidden places excluded): by
category with hours / prices / photos / phone / website, by source (OSM, Overture, Foursquare,
hand-made), and which source owns each tracked field (place_field_sources). Markdown output.
Raw parameterized SQL (SSOT §14.1).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import List, Sequence

HERE = Path(__file__).resolve().parent

IN_REGION = """
FROM places p
JOIN regions r ON r.id = %(region)s AND ST_Covers(r.boundary, p.geom::geometry)
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.status <> 'hidden'
"""

BY_CATEGORY = (
    """
SELECT coalesce(c.slug, '(none)') AS slug, count(*) AS total,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM place_hours h
                        WHERE h.place_id = p.id)) AS hours,
       count(*) FILTER (WHERE p.entry_price_kzt IS NOT NULL OR p.avg_check_kzt IS NOT NULL
                        OR p.price_per_night_kzt IS NOT NULL) AS prices,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM place_photos f
                        WHERE f.place_id = p.id AND f.status = 'approved')) AS photos,
       count(*) FILTER (WHERE p.phone IS NOT NULL) AS phone,
       count(*) FILTER (WHERE p.website IS NOT NULL) AS website
"""
    + IN_REGION
    + "GROUP BY 1 ORDER BY 2 DESC, 1"
)

TOTALS = (
    """
SELECT count(*), count(*) FILTER (WHERE p.name_ru IS NOT NULL),
       count(*) FILTER (WHERE p.name_en IS NOT NULL),
       count(*) FILTER (WHERE p.address_ru IS NOT NULL OR p.address_en IS NOT NULL),
       count(*) FILTER (WHERE p.is_partner)
"""
    + IN_REGION
)

# a place can have several sources (merged duplicates), so the rows do not add up to the total
BY_SOURCE = (
    """
SELECT src, count(*) FROM (
    SELECT p.id, unnest(
        (CASE WHEN p.osm_id IS NOT NULL THEN ARRAY['osm'] ELSE ARRAY[]::text[] END)
        || coalesce((SELECT array_agg(e.source) FROM place_external_ids e WHERE e.place_id = p.id),
                    ARRAY[]::text[])
        || (CASE WHEN p.osm_id IS NULL AND NOT EXISTS (
                    SELECT 1 FROM place_external_ids e WHERE e.place_id = p.id)
                 THEN ARRAY['manual'] ELSE ARRAY[]::text[] END)) AS src
"""
    + IN_REGION
    + """) s GROUP BY src ORDER BY 2 DESC, 1"""
)
MULTI_SOURCE = (
    """
SELECT count(*) FROM (
    SELECT p.id, (CASE WHEN p.osm_id IS NOT NULL THEN 1 ELSE 0 END)
           + (SELECT count(DISTINCT e.source) FROM place_external_ids e
              WHERE e.place_id = p.id) AS n
"""
    + IN_REGION
    + """) s WHERE n >= 2"""
)

FIELD_SOURCES = """
SELECT f.field, f.source, count(*)
FROM place_field_sources f JOIN places p ON p.id = f.place_id
JOIN regions r ON r.id = %(region)s AND ST_Covers(r.boundary, p.geom::geometry)
WHERE p.status <> 'hidden'
GROUP BY 1, 2 ORDER BY 1, 3 DESC, 2
"""


def _pct(part: int, whole: int) -> str:
    return f"{part} ({100 * part / whole:.0f}%)" if whole else str(part)


def _table(header: Sequence[str], rows: Sequence[Sequence]) -> List[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


def build_report(conn, region_id: str) -> str:
    params = {"region": region_id}
    region = conn.execute("SELECT name_ru, name_en FROM regions WHERE id = %s", (region_id,))
    row = region.fetchone()
    if row is None:
        raise SystemExit(f"unknown region {region_id!r}")
    total, ru, en, addr, partners = conn.execute(TOTALS, params).fetchone()

    lines = [f"# Покрытие данными мест: {row[0]} ({region_id})", ""]
    lines.append(f"Отчёт на {date.today().isoformat()}; места внутри границы региона, без скрытых.")
    lines += ["", "## Итого", ""]
    lines += _table(
        ["Мест", "С названием RU", "С названием EN", "С адресом", "Партнёров"],
        [[total, _pct(ru, total), _pct(en, total), _pct(addr, total), partners]],
    )

    lines += ["", "## По категориям", ""]
    cats = conn.execute(BY_CATEGORY, params).fetchall()
    lines += _table(
        ["Категория", "Мест", "С часами", "С ценами", "С фото", "С телефоном", "С сайтом"],
        [
            [slug, n, _pct(h, n), _pct(pr, n), _pct(ph, n), _pct(tel, n), _pct(web, n)]
            for slug, n, h, pr, ph, tel, web in cats
        ],
    )

    lines += ["", "## По источникам", ""]
    sources = conn.execute(BY_SOURCE, params).fetchall()
    lines += _table(["Источник", "Мест"], [[s, n] for s, n in sources])
    multi = conn.execute(MULTI_SOURCE, params).fetchone()[0]
    lines += ["", f"Мест, склеенных из двух и более источников: {multi}. "
              "Одно место может входить в несколько строк таблицы выше.", ""]  # fmt: skip

    lines += ["", "## Чьё значение у поля", ""]
    owners = conn.execute(FIELD_SOURCES, params).fetchall()
    lines += _table(["Поле", "Источник значения", "Мест"], [list(r) for r in owners])
    lines += [
        "",
        "Деление по городам и областям не считается: в базе нет административных границ "
        "мест, только граница региона.",
        "",
    ]
    return "\n".join(lines)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = HERE.parent.parent / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    return url


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--region", required=True)
    ap.add_argument("--out", help="also write the markdown to this file")
    args = ap.parse_args(argv)

    import psycopg

    with psycopg.connect(database_url()) as conn:
        text = build_report(conn, args.region)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
