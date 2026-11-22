#!/usr/bin/env bash
# Ш-11/Ш-59: Kazakhstan OSM extract -> Planetiler (OpenMapTiles schema) -> maps/build/kazakhstan.pmtiles
# One command:  ./maps/build_tiles.sh        (or `make tiles`)  - whole country (default)
# Almaty only:  AREA=almaty ./maps/build_tiles.sh   (or `make tiles-almaty`) -> almaty.pmtiles
# Overrides:    OUT_NAME, BOUNDS, BUILD_DIR (dir with the pbf and sources/), MAXZOOM, SKIP_FETCH=1 (use existing pbf)
# Runner: Docker image if the docker daemon is up, else the Planetiler jar (needs Java 21+).
# Force a runner:  RUNNER=docker|jar ./maps/build_tiles.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="${BUILD_DIR:-$HERE/build}"
PBF_URL="${PBF_URL:-https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf}"
PBF="$BUILD/kazakhstan.osm.pbf"
AREA="${AREA:-kazakhstan}"
case "$AREA" in
  # Almaty + mountain suburbs (Medeu, Shymbulak, Big Almaty Lake, Kok-Zhailau). lon_min,lat_min,lon_max,lat_max
  almaty) DEF_BOUNDS="76.6,42.95,77.35,43.45" ;;
  # Whole Kazakhstan (bbox of the `kazakhstan` region, db/migrations 0031)
  kazakhstan) DEF_BOUNDS="46.4,40.5,87.4,55.5" ;;
  *) echo "ERROR: unknown AREA=$AREA (kazakhstan|almaty)" >&2; exit 1 ;;
esac
BOUNDS="${BOUNDS:-$DEF_BOUNDS}"
OUT_NAME="${OUT_NAME:-$AREA.pmtiles}"
MAXZOOM="${MAXZOOM:-14}"
OUT="$BUILD/$OUT_NAME"
LANGS="${LANGS:-ru,en}"
# Pinned by digest for reproducible tiles (this is the build verified on 2026-11-21, Planetiler 0.10.3-SNAPSHOT).
PLANETILER_IMAGE="${PLANETILER_IMAGE:-ghcr.io/onthegomap/planetiler@sha256:f8b31ff4985dfd29421670296ba4f70b3e12c8fecc18e091b4058ab228f8c049}"
PLANETILER_JAR_URL="${PLANETILER_JAR_URL:-https://github.com/onthegomap/planetiler/releases/latest/download/planetiler.jar}"
JAR="$BUILD/planetiler.jar"

mkdir -p "$BUILD"

# One shared extract for tiles, places/transit import and Valhalla: data/osm/cache (make osm-pbf).
SHARED_PBF="$HERE/../data/osm/cache/kazakhstan.osm.pbf"
if [ "${SKIP_FETCH:-0}" = 1 ] && [ -s "$PBF" ]; then
  echo ">> SKIP_FETCH=1: keeping existing $PBF"
else
  PBF_URL="$PBF_URL" REFRESH="${REFRESH:-0}" "$HERE/../data/osm/fetch_pbf.sh"
  # Planetiler (docker) only sees $BUILD, so expose the shared file there via a hard link.
  if [ ! "$PBF" -ef "$SHARED_PBF" ]; then
    rm -f "$PBF"
    ln "$SHARED_PBF" "$PBF" 2>/dev/null || cp "$SHARED_PBF" "$PBF"
  fi
fi
echo ">> using $PBF"

# Planetiler args shared by both runners. {DIR} is replaced by the build dir as seen by the runner.
args() {
  local d="$1"
  echo "--osm-path=$d/kazakhstan.osm.pbf" "--output=$d/$OUT_NAME" \
       "--bounds=$BOUNDS" "--languages=$LANGS" \
       "--download" "--download-dir=$d/sources" "--tmpdir=$d/tmp" \
       "--force" "--maxzoom=$MAXZOOM"
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
