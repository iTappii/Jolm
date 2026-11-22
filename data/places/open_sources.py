"""Read Overture Maps Places and Foursquare OS Places Parquet files into common records (Ш-58).

A record is a dict:
    source ('overture' | 'foursquare'), external_id, lon, lat, category (project slug),
    name_ru, name_en, name_kk, address_ru, address_en, website, phone.
Records without a name, without coordinates or without a mapped category (categories.py) are
skipped; so are permanently closed places and Overture places below MIN_CONFIDENCE.
The files are read with DuckDB (extra `places`); nothing here touches the network.

Licences: Overture Maps Foundation places - CDLA-Permissive-2.0 (attribution required);
Foursquare OS Places - Apache-2.0 (attribution required). Both are shown in "About" (Ш-52/58).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from open_categories import foursquare_category, overture_category
from tag_mapping import pick_names

MIN_CONFIDENCE = 0.5
_CYR = re.compile(r"[Ѐ-ӿ]")

OVERTURE_SQL = """
SELECT id, lon, lat, names.primary AS name, taxonomy.hierarchy AS hierarchy,
       taxonomy.primary AS tprimary, confidence, operating_status,
       addresses[1].freeform AS address, websites[1] AS website, phones[1] AS phone
FROM read_parquet(?)
"""


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def address_fields(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """(address_ru, address_en): Cyrillic text goes to RU, anything else to EN."""
    text = _clean(text)
    if not text:
        return None, None
    return (text, None) if _CYR.search(text) else (None, text)


def build_record(
    source: str,
    external_id: str,
    lon,
    lat,
    category: Optional[str],
    name: Optional[str],
    address: Optional[str] = None,
    website: Optional[str] = None,
    phone: Optional[str] = None,
) -> Optional[Dict]:
    name = _clean(name)
    if not (external_id and name and category and lon is not None and lat is not None):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    ru, en, kk = pick_names({"name": name})
    if not (ru or en or kk):
        return None
    addr_ru, addr_en = address_fields(address)
    return {
        "source": source,
        "external_id": str(external_id),
        "lon": float(lon),
        "lat": float(lat),
        "category": category,
        "name_ru": ru,
        "name_en": en,
        "name_kk": kk,
        "address_ru": addr_ru,
        "address_en": addr_en,
        "website": _clean(website),
        "phone": _clean(phone),
    }


def _query(path: Path, sql: str) -> Iterator[tuple]:
    import duckdb

    con = duckdb.connect()
    try:
        cur = con.execute(sql, [str(path)])
        while True:
            rows = cur.fetchmany(20000)
            if not rows:
                break
            yield from rows
    finally:
        con.close()


def read_overture(path: Path, min_confidence: float = MIN_CONFIDENCE) -> Iterator[Dict]:
    """Records of an Overture places Parquet file (columns of fetch_overture.py)."""
    for (
        pid, lon, lat, name, hierarchy, tprimary, confidence, status, address, website, phone,
    ) in _query(path, OVERTURE_SQL):  # fmt: skip
        if status == "closed" or (confidence is not None and confidence < min_confidence):
            continue
        rec = build_record(
            "overture", pid, lon, lat, overture_category(hierarchy, tprimary), name, address,
            website, phone,
        )  # fmt: skip
        if rec:
            yield rec


def _foursquare_sql(columns: List[str]) -> str:
    def col(name: str, alt: str = "NULL") -> str:
        return name if name in columns else alt

    labels = col("fsq_category_labels")
    return f"""
SELECT {col("fsq_place_id")} AS id, {col("longitude")} AS lon, {col("latitude")} AS lat,
       {col("name")} AS name, {labels} AS labels, {col("date_closed")} AS date_closed,
       {col("address")} AS address, {col("website")} AS website, {col("tel")} AS phone
FROM read_parquet(?)
"""


def foursquare_columns(path: Path) -> List[str]:
    import duckdb

    con = duckdb.connect()
    try:
        rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def read_foursquare(path: Path) -> Iterator[Dict]:
    """Records of a Foursquare OS Places Parquet file (official schema, one or many files)."""
    columns = foursquare_columns(path)
    for pid, lon, lat, name, labels, date_closed, address, website, phone in _query(
        path, _foursquare_sql(columns)
    ):
        if date_closed:
            continue
        rec = build_record(
            "foursquare", pid, lon, lat, foursquare_category(labels), name, address, website, phone
        )  # fmt: skip
        if rec:
            yield rec


def summarize(records: List[Dict]) -> Counter:
    return Counter(r["category"] for r in records)
