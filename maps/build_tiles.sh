#!/usr/bin/env bash
# Ш-11: Kazakhstan OSM extract -> Planetiler (OpenMapTiles schema) -> maps/build/almaty.pmtiles
# One command:  ./maps/build_tiles.sh        (or `make tiles`)
# Runner: Docker image if the docker daemon is up, else the Planetiler jar (needs Java 21+).
# Force a runner:  RUNNER=docker|jar ./maps/build_tiles.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$HERE/build"
PBF_URL="${PBF_URL:-https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf}"
PBF="$BUILD/kazakhstan.osm.pbf"
OUT="$BUILD/almaty.pmtiles"
# Almaty + mountain suburbs (Medeu, Shymbulak, Big Almaty Lake, Kok-Zhailau). lon_min,lat_min,lon_max,lat_max
BOUNDS="${BOUNDS:-76.6,42.95,77.35,43.45}"
LANGS="${LANGS:-ru,en}"
# Pinned by digest for reproducible tiles (this is the build verified on 2026-11-21, Planetiler 0.10.3-SNAPSHOT).
PLANETILER_IMAGE="${PLANETILER_IMAGE:-ghcr.io/onthegomap/planetiler@sha256:f8b31ff4985dfd29421670296ba4f70b3e12c8fecc18e091b4058ab228f8c049}"
PLANETILER_JAR_URL="${PLANETILER_JAR_URL:-https://github.com/onthegomap/planetiler/releases/latest/download/planetiler.jar}"
JAR="$BUILD/planetiler.jar"

mkdir -p "$BUILD"

if [ ! -s "$PBF" ] || [ "${REFRESH:-0}" = "1" ]; then
  echo ">> downloading $PBF_URL"
  curl -fL --retry 3 -C - -o "$PBF.part" "$PBF_URL"
  mv "$PBF.part" "$PBF"
else
  echo ">> using existing $PBF (REFRESH=1 to re-download)"
fi

# Planetiler args shared by both runners. {DIR} is replaced by the build dir as seen by the runner.
args() {
  local d="$1"
  echo "--osm-path=$d/kazakhstan.osm.pbf" "--output=$d/almaty.pmtiles" \
       "--bounds=$BOUNDS" "--languages=$LANGS" \
       "--download" "--download-dir=$d/sources" "--tmpdir=$d/tmp" \
       "--force" "--maxzoom=14"
}

RUNNER="${RUNNER:-auto}"
if [ "$RUNNER" = "auto" ]; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    RUNNER=docker
  elif command -v java >/dev/null 2>&1; then
    RUNNER=jar
  else
    echo "ERROR: need either a running Docker daemon or Java 21+ (no runner found)" >&2
    exit 1
  fi
fi

case "$RUNNER" in
  docker)
    echo ">> planetiler via docker ($PLANETILER_IMAGE)"
    # shellcheck disable=SC2046
    docker run --rm -v "$BUILD:/data" "$PLANETILER_IMAGE" $(args /data)
    ;;
  jar)
    major="$(java -version 2>&1 | sed -n '1s/.*"\([0-9]*\).*/\1/p')"
    if [ "${major:-0}" -lt 21 ]; then echo "ERROR: Java 21+ required, found $major" >&2; exit 1; fi
    if [ ! -s "$JAR" ]; then
      echo ">> downloading planetiler.jar"
      curl -fL --retry 3 -o "$JAR.part" "$PLANETILER_JAR_URL"
      mv "$JAR.part" "$JAR"
    fi
    echo ">> planetiler via jar (Java $major)"
    # shellcheck disable=SC2046
    java -Xmx"${JAVA_XMX:-4g}" -jar "$JAR" $(args "$BUILD")
    ;;
  *) echo "ERROR: unknown RUNNER=$RUNNER" >&2; exit 1 ;;
esac

ls -lh "$OUT"
echo ">> done: $OUT"
