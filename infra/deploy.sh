#!/usr/bin/env bash
# Build / push / migrate / roll the API + worker (Ш-51). No provider lock-in: it needs only Docker
# (and a registry if you push). Point it at a remote host with DOCKER_HOST=ssh://user@host or a
# docker context; everything is parameterised by environment variables:
#
#   ENV_FILE    env file of this environment            (default: .env.prod; staging: .env.staging)
#   REGISTRY    image registry prefix, e.g. ghcr.io/org (empty = local image only)
#   IMAGE_NAME  image name                              (default: jol-api)
#   TAG         image tag                               (default: git short sha, "-dirty" if changed)
#   PROJECT     compose project name                    (default: jol-prod; use jol-staging for staging)
#   BACKUP_BEFORE_MIGRATE=1  run infra/backup.sh before applying migrations
#
# Usage: infra/deploy.sh <command>
#   build      build the image (never pushes)
#   push       push REGISTRY/IMAGE_NAME:TAG (explicit; `up` never pushes)
#   check      validate secrets with the image (python -m app.auth.keys check)
#   migrate    apply db/migrations once with the image
#   up         check + (backup) + migrate + start/roll api and worker, wait for readiness
#   rollback   roll back to the previous tag (code only: migrations are forward-only)
#   status     show containers and the recorded tags
#   logs       follow api + worker logs
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE="${ENV_FILE:-.env.prod}"
IMAGE_NAME="${IMAGE_NAME:-jol-api}"
PROJECT="${PROJECT:-jol-prod}"
STATE_DIR="${STATE_DIR:-infra/.deploy-state}"
if [[ -z "${TAG:-}" ]]; then
  TAG="$(git rev-parse --short HEAD 2>/dev/null || echo local)"
  git diff --quiet 2>/dev/null || TAG="${TAG}-dirty"
fi
IMAGE="${REGISTRY:+${REGISTRY%/}/}${IMAGE_NAME}:${TAG}"
COMPOSE=(docker compose -p "$PROJECT" -f infra/docker-compose.prod.yml)

die() { echo "deploy: $*" >&2; exit 1; }
need_env() { [[ -f "$ENV_FILE" ]] || die "$ENV_FILE not found (copy infra/env.prod.example)"; }

# compose <image> <args...>; the compose file lives in infra/, so a relative ENV_FILE is ../ from there
compose() {
  local ef="$ENV_FILE"
  [[ "$ef" == /* ]] || ef="../$ef"
  ENV_FILE="$ef" JOL_IMAGE="$1" "${COMPOSE[@]}" --env-file "$ENV_FILE" "${@:2}"
}

record_tag() { mkdir -p "$STATE_DIR"; echo "$1" >> "$STATE_DIR/$PROJECT.tags"; }
current_tag() { tail -n 1 "$STATE_DIR/$PROJECT.tags" 2>/dev/null || true; }
previous_tag() { tail -n 2 "$STATE_DIR/$PROJECT.tags" 2>/dev/null | head -n 1; }

wait_ready() {
  local image="$1" i
  for i in $(seq 1 60); do
    if compose "$image" exec -T api python -c \
      "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2).status == 200 else 1)" \
      >/dev/null 2>&1; then
      echo "deploy: api is ready ($image)"; return 0
    fi
    sleep 2
  done
  return 1
}

cmd="${1:-}"
case "$cmd" in
  build)
    docker build -f infra/Dockerfile.api -t "$IMAGE" ${EXTRAS:+--build-arg "EXTRAS=$EXTRAS"} .
    echo "built $IMAGE" ;;
  push)
    [[ -n "${REGISTRY:-}" ]] || die "set REGISTRY to push"
    docker push "$IMAGE" ;;
  check)
    need_env
    docker run --rm --env-file "$ENV_FILE" "$IMAGE" python -m app.auth.keys check ;;
  migrate)
    need_env
    compose "$IMAGE" run --rm migrate ;;
  up)
    need_env
    docker image inspect "$IMAGE" >/dev/null 2>&1 || die "image $IMAGE not found locally: run build (or docker pull)"
    docker run --rm --env-file "$ENV_FILE" "$IMAGE" python -m app.auth.keys check
    compose "$IMAGE" up -d --wait postgres
    if [[ "${BACKUP_BEFORE_MIGRATE:-0}" == "1" ]]; then
      infra/backup.sh
    fi
    compose "$IMAGE" run --rm migrate
    compose "$IMAGE" up -d valhalla api worker
    if wait_ready "$IMAGE"; then
      record_tag "$TAG"
      echo "deploy: $PROJECT now runs $IMAGE"
    else
      echo "deploy: api did not become ready; recent logs:" >&2
      compose "$IMAGE" logs --tail 50 api >&2 || true
      echo "deploy: roll back with: infra/deploy.sh rollback" >&2
      exit 1
    fi ;;
  rollback)
    need_env
    prev="$(previous_tag)"
    [[ -n "$prev" ]] || die "no previous tag recorded in $STATE_DIR/$PROJECT.tags"
    PREV_IMAGE="${REGISTRY:+${REGISTRY%/}/}${IMAGE_NAME}:${prev}"
    echo "deploy: rolling back to $PREV_IMAGE (database migrations are NOT reverted)"
    compose "$PREV_IMAGE" up -d api worker
    wait_ready "$PREV_IMAGE" || die "rolled back image is not ready either"
    record_tag "$prev" ;;
  status)
    echo "current tag: $(current_tag)  previous: $(previous_tag)"
    compose "${IMAGE}" ps ;;
  logs)
    compose "$IMAGE" logs -f --tail 100 api worker ;;
  *)
    sed -n '2,26p' "$0"; exit 2 ;;
esac
