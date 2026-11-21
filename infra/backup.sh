#!/usr/bin/env bash
# Logical backup of the Jol database to S3-compatible storage (Ш-51).
#
#   DATABASE_URL         postgres:// URL (or PG_DOCKER_CONTAINER + PG_USER + BACKUP_DB, see pg-common.sh)
#   BACKUP_S3_BUCKET     target bucket; empty = keep the file in BACKUP_DIR only
#   BACKUP_S3_PREFIX     key prefix                                  (default: jol/backups)
#   BACKUP_S3_ENDPOINT   endpoint URL for non-AWS S3 services        (optional)
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION   credentials for the `aws` CLI
#   BACKUP_DIR           local staging directory                     (default: ./backups)
#   BACKUP_KEEP_LOCAL    local files to keep                         (default: 3)
#   BACKUP_DB            database name (default: from DATABASE_URL, else "jol")
#
# Output: jol-<UTC timestamp>.dump (pg_dump custom format) + .sha256, uploaded together.
# This is a LOGICAL backup (daily-ish). Point-in-time recovery needs WAL archiving or a managed
# database with PITR: a hosting requirement, see docs/deploy.md. Retention in the bucket is the
# bucket's lifecycle rule (also docs/deploy.md); this script only prunes its local directory.
# Run from cron / a scheduler; a non-zero exit is the alert. Restore: infra/restore.sh.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=pg-common.sh
. "$here/pg-common.sh"

if [[ -z "${PG_DOCKER_CONTAINER:-}" && -f "$here/../.env" && -z "${DATABASE_URL:-}" ]]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "$here/../.env" | head -1 | cut -d= -f2-)"
fi
DB="${BACKUP_DB:-}"
if [[ -z "$DB" ]]; then
  DB="$( [[ -n "${DATABASE_URL:-}" ]] && db_name_of "$DATABASE_URL" || echo jol )"
fi
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
file="$BACKUP_DIR/jol-$stamp.dump"

pg_dump_to "$DB" "$file"
[[ -s "$file" ]] || die "dump is empty"
( cd "$BACKUP_DIR" && sha256 "$(basename "$file")" > "$(basename "$file").sha256" )
echo "dumped $DB -> $file ($(wc -c < "$file" | tr -d ' ') bytes)"

if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
  prefix="${BACKUP_S3_PREFIX:-jol/backups}"
  aws_args=()
  [[ -n "${BACKUP_S3_ENDPOINT:-}" ]] && aws_args+=(--endpoint-url "$BACKUP_S3_ENDPOINT")
  dest="s3://$BACKUP_S3_BUCKET/$prefix/$(basename "$file")"
  aws ${aws_args[@]+"${aws_args[@]}"} s3 cp --only-show-errors "$file" "$dest"
  aws ${aws_args[@]+"${aws_args[@]}"} s3 cp --only-show-errors "$file.sha256" "$dest.sha256"
  echo "uploaded $dest"
else
  echo "BACKUP_S3_BUCKET is empty: the backup stays in $BACKUP_DIR only"
fi

keep="${BACKUP_KEEP_LOCAL:-3}"
ls -1t "$BACKUP_DIR"/jol-*.dump 2>/dev/null | tail -n +"$((keep + 1))" | while read -r old; do
  rm -f "$old" "$old.sha256"
done
