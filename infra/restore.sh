#!/usr/bin/env bash
# Restore a backup made by infra/backup.sh into a NEW database (Ш-51).
#
# Usage: infra/restore.sh <dump file | s3://bucket/key.dump> <target database>
#   env: DATABASE_URL (server to restore on; the target database name is replaced)
#        BACKUP_S3_ENDPOINT, AWS_* for s3:// sources; PG_DOCKER_CONTAINER / PG_USER as in backup.sh
#        VERIFY_SOURCE_URL  if set, compare row counts of every public table with this database
#                           after the restore (infra/verify_restore.py); non-zero exit on a mismatch
#        DROP_SCRATCH=1     drop the target database again after verifying (scratch runs)
#
# Safety: it only creates `target`; if it already exists it refuses, unless the name ends in
# `_scratch` or `_restore` (then it is recreated). It never touches any other database. To
# restore into production, restore to a new name, check it, then switch DATABASE_URL (or rename).
# The dump is made with --no-owner: objects belong to the user that runs the restore.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=pg-common.sh
. "$here/pg-common.sh"

src="${1:-}"; target="${2:-}"
[[ -n "$src" && -n "$target" ]] || { sed -n '2,16p' "$0"; exit 2; }
[[ "$target" =~ ^[a-z][a-z0-9_]*$ ]] || die "bad database name: $target"
if [[ -z "${PG_DOCKER_CONTAINER:-}" && -f "$here/../.env" && -z "${DATABASE_URL:-}" ]]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "$here/../.env" | head -1 | cut -d= -f2-)"
fi

tmp=""
cleanup() { [[ -n "$tmp" ]] && rm -rf "$tmp"; return 0; }
trap cleanup EXIT

if [[ "$src" == s3://* ]]; then
  tmp="$(mktemp -d)"
  aws_args=()
  [[ -n "${BACKUP_S3_ENDPOINT:-}" ]] && aws_args+=(--endpoint-url "$BACKUP_S3_ENDPOINT")
  aws ${aws_args[@]+"${aws_args[@]}"} s3 cp --only-show-errors "$src" "$tmp/restore.dump"
  aws ${aws_args[@]+"${aws_args[@]}"} s3 cp --only-show-errors "$src.sha256" "$tmp/restore.dump.sha256" || true
  file="$tmp/restore.dump"
  [[ -f "$file.sha256" ]] && { ( cd "$tmp" && sed 's|  .*|  restore.dump|' restore.dump.sha256 | sha256 -c - ) || die "checksum mismatch"; }
else
  file="$src"
  [[ -f "$file" ]] || die "no such file: $file"
  if [[ -f "$file.sha256" ]]; then
    ( cd "$(dirname "$file")" && sha256 -c "$(basename "$file").sha256" ) || die "checksum mismatch"
  fi
fi

exists="$(pg_admin "SELECT 1 FROM pg_database WHERE datname = '$target'")"
if [[ -n "$exists" ]]; then
  if [[ "$target" == *_scratch || "$target" == *_restore ]]; then
    pg_admin "DROP DATABASE \"$target\" WITH (FORCE)"
  else
    die "database $target already exists; restore into a new name"
  fi
fi
pg_admin "CREATE DATABASE \"$target\""
pg_restore_from "$target" "$file"
echo "restored $file -> $target"

status=0
if [[ -n "${VERIFY_SOURCE_URL:-}" ]]; then
  restored_url="$(url_with_db "${DATABASE_URL:?set DATABASE_URL}" "$target")"
  python3 "$here/verify_restore.py" "$VERIFY_SOURCE_URL" "$restored_url" || status=$?
fi
if [[ "${DROP_SCRATCH:-0}" == "1" ]]; then
  [[ "$target" == *_scratch || "$target" == *_restore ]] || die "DROP_SCRATCH only for *_scratch / *_restore"
  pg_admin "DROP DATABASE \"$target\" WITH (FORCE)"
  echo "dropped $target"
fi
exit "$status"
