"""Own forward-only migration runner (no ORM, plain .sql files).

Usage: python db/migrate.py [--dir db/migrations]

- Files: ``NNNN_description.sql`` applied in numeric order, each in its own transaction.
- ``schema_migrations(version, applied_at, checksum)`` records what was applied.
- If an already applied file changed on disk (sha256 differs), the run fails.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
FILE_RE = re.compile(r"^(\d{4,})_[A-Za-z0-9_\-]+\.sql$")
LOCK_KEY = 726_001  # arbitrary advisory-lock id: serialises concurrent runners

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text        PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now(),
    checksum   text        NOT NULL
)
"""


class MigrationError(RuntimeError):
    pass


def checksum_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover(directory: Path) -> list[tuple[str, Path]]:
    found = []
    for path in sorted(directory.glob("*.sql")):
        if not FILE_RE.match(path.name):
            raise MigrationError(f"bad migration file name: {path.name}")
        found.append((path.stem, path))
    versions = [v for v, _ in found]
    if len(set(v.split("_", 1)[0] for v in versions)) != len(versions):
        raise MigrationError("duplicate migration number")
    return found


def apply_migrations(conninfo: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations. Returns the versions applied in this run."""
    files = discover(Path(directory))
    applied_now: list[str] = []
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            conn.execute(CREATE_TABLE_SQL)
            applied = dict(
                conn.execute("SELECT version, checksum FROM schema_migrations").fetchall()
            )
            # applied files must still exist and be unchanged
            on_disk = {v for v, _ in files}
            for version in applied:
                if version not in on_disk:
                    raise MigrationError(f"applied migration {version} is missing on disk")
            for version, path in files:
                text = path.read_text(encoding="utf-8")
                digest = checksum_of(text)
                if version in applied:
                    if applied[version] != digest:
                        raise MigrationError(
                            f"checksum mismatch for applied migration {version}: "
                            "applied files must not be edited (add a new migration)"
                        )
                    continue
                with conn.transaction():
                    conn.execute(text)  # no params -> multi-statement script allowed
                    conn.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                        (version, digest),
                    )
                applied_now.append(version)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
    return applied_now


def main() -> int:
    conninfo = os.environ.get("DATABASE_URL")
    if not conninfo:
        env = Path(__file__).resolve().parent.parent / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    conninfo = line.split("=", 1)[1].strip()
    if not conninfo:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    directory = MIGRATIONS_DIR
    if "--dir" in sys.argv:
        directory = Path(sys.argv[sys.argv.index("--dir") + 1])
    try:
        applied = apply_migrations(conninfo, directory)
    except MigrationError as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1
    print("applied: " + ", ".join(applied) if applied else "nothing to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
