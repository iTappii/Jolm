"""Load categories, curated popular places, and transport tariffs into the dev DB.

Usage: python data/seed/load_seed.py   (DATABASE_URL from env or .env)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import import_popular  # noqa: E402


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


def main() -> int:
    with psycopg.connect(database_url()) as conn:
        conn.execute((HERE / "categories.sql").read_text(encoding="utf-8"))
        n = conn.execute("SELECT count(*) FROM place_categories").fetchone()[0]
        print(f"categories: {n}")
        stats = import_popular.import_csv(conn, HERE / "popular_places.csv")
        print(f"popular places: {stats}")
        conn.execute((HERE / "transport_tariffs.sql").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
