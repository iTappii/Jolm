"""Compare row counts of every public table of two databases (Ш-51 restore check).

Usage: python infra/verify_restore.py <source url> <restored url>
Exit 0 when every table has the same count, 1 otherwise (differences are listed). A source that
is being written to while it is dumped may differ in busy tables (jobs, analytics, rate limits):
those are listed as such, so rerun against a quiet source or a snapshot. Needs psycopg (the
server venv has it). Also checks that PostGIS and the migration table came across.
"""

import sys

import psycopg
from psycopg import sql


def counts(url):
    out = {}
    with psycopg.connect(url) as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
            )
        ]
        for table in tables:
            out[table] = conn.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            ).fetchone()[0]
        ext = {r[0] for r in conn.execute("SELECT extname FROM pg_extension")}
        last = conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
    return out, ext, last


def main(argv):
    src, dst = counts(argv[0]), counts(argv[1])
    (a, ext_a, last_a), (b, ext_b, last_b) = src, dst
    bad = []
    for table in sorted(set(a) | set(b)):
        marker = "ok " if a.get(table) == b.get(table) else "DIFF"
        if marker == "DIFF":
            bad.append(table)
        print("%s %-32s source=%-9s restored=%s" % (marker, table, a.get(table), b.get(table)))
    print(
        "tables: %d source / %d restored; rows: %d / %d"
        % (len(a), len(b), sum(a.values()), sum(b.values()))
    )
    print("latest migration: %s / %s" % (last_a, last_b))
    if "postgis" in ext_a and "postgis" not in ext_b:
        bad.append("extension postgis")
    if last_a != last_b:
        bad.append("schema_migrations")
    if bad:
        print("MISMATCH: " + ", ".join(bad))
        return 1
    print("restore verified: every table has the same row count")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
