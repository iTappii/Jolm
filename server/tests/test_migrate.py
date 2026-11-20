import psycopg
import pytest

from migrate import MigrationError, apply_migrations
from tests.conftest import ROOT

MIGRATIONS = ROOT / "db" / "migrations"


def test_applies_on_empty_db_and_rerun_is_noop(scratch_db_url):
    first = apply_migrations(scratch_db_url, MIGRATIONS)
    assert first and first[0] == "0001_init"
    assert apply_migrations(scratch_db_url, MIGRATIONS) == []
    with psycopg.connect(scratch_db_url) as conn:
        exts = {r[0] for r in conn.execute("SELECT extname FROM pg_extension")}
        assert {"postgis", "pgcrypto", "citext"} <= exts
        assert conn.execute("SELECT to_regclass('public.jobs')").fetchone()[0] == "jobs"
        count = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
        assert count == len(first)


def test_changed_checksum_fails(scratch_db_url, tmp_path):
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE a (id int);")
    assert apply_migrations(scratch_db_url, tmp_path) == ["0001_a"]
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE a (id int, extra int);")
    with pytest.raises(MigrationError, match="checksum mismatch"):
        apply_migrations(scratch_db_url, tmp_path)


def test_new_migration_applied_and_failure_rolls_back(scratch_db_url, tmp_path):
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE a (id int);")
    apply_migrations(scratch_db_url, tmp_path)
    (tmp_path / "0002_bad.sql").write_text("CREATE TABLE b (id int); SELECT 1/0;")
    with pytest.raises(psycopg.errors.DivisionByZero):
        apply_migrations(scratch_db_url, tmp_path)
    with psycopg.connect(scratch_db_url) as conn:
        assert conn.execute("SELECT to_regclass('public.b')").fetchone()[0] is None
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
        assert versions == ["0001_a"]
