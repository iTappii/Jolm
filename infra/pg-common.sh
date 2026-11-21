# Sourced by backup.sh / restore.sh. PostgreSQL client commands, either local binaries or inside a
# running container (handy where only Docker is installed):
#   PG_DOCKER_CONTAINER=jol-postgres-1  PG_USER=jol  -> `docker exec` into that container
#   otherwise pg_dump / pg_restore / psql from PATH, connecting with DATABASE_URL (or libpq PG* vars)
# Override a binary with PG_DUMP / PG_RESTORE / PSQL.

die() { echo "$(basename "$0"): $*" >&2; exit 1; }

PG_USER="${PG_USER:-jol}"

# sha256 <args>: sha256sum (Linux) or shasum -a 256 (macOS)
sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }

# db_name <url>: database name of a postgres:// URL
db_name_of() { python3 - "$1" <<'PY'
import sys
from urllib.parse import urlparse
print(urlparse(sys.argv[1]).path.lstrip("/"))
PY
}

# url_with_db <url> <db>: the same server, another database
url_with_db() { python3 - "$1" "$2" <<'PY'
import sys
from urllib.parse import urlparse, urlunparse
u = urlparse(sys.argv[1])
print(urlunparse(u._replace(path="/" + sys.argv[2])))
PY
}

# pg_dump_to <db> <outfile>   (custom format, compressed, restorable with pg_restore)
pg_dump_to() {
  local db="$1" out="$2"
  if [[ -n "${PG_DOCKER_CONTAINER:-}" ]]; then
    docker exec -i "$PG_DOCKER_CONTAINER" pg_dump -U "$PG_USER" -d "$db" -Fc --no-owner --no-acl > "$out"
  else
    "${PG_DUMP:-pg_dump}" "$(url_with_db "${DATABASE_URL:?set DATABASE_URL}" "$db")" -Fc --no-owner --no-acl -f "$out"
  fi
}

# pg_restore_from <db> <file>
pg_restore_from() {
  local db="$1" file="$2"
  if [[ -n "${PG_DOCKER_CONTAINER:-}" ]]; then
    docker exec -i "$PG_DOCKER_CONTAINER" pg_restore -U "$PG_USER" -d "$db" --no-owner --no-acl --exit-on-error < "$file"
  else
    "${PG_RESTORE:-pg_restore}" -d "$(url_with_db "${DATABASE_URL:?set DATABASE_URL}" "$db")" --no-owner --no-acl --exit-on-error "$file"
  fi
}

# pg_admin <sql>: run one statement on the maintenance database
pg_admin() {
  if [[ -n "${PG_DOCKER_CONTAINER:-}" ]]; then
    docker exec -i "$PG_DOCKER_CONTAINER" psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 -qAt -c "$1"
  else
    "${PSQL:-psql}" "$(url_with_db "${DATABASE_URL:?set DATABASE_URL}" postgres)" -v ON_ERROR_STOP=1 -qAt -c "$1"
  fi
}
