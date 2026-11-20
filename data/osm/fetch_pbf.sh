#!/usr/bin/env bash
# One shared OSM extract for everything: places import, transit import, Valhalla.
# -> data/osm/cache/kazakhstan.osm.pbf  (gitignored). `make osm-pbf` runs this.
# Reuses maps/build/kazakhstan.osm.pbf (hard link, else copy) instead of re-downloading 227 MB.
# REFRESH=1 forces a new download. PBF_URL overrides the source (Geofabrik Kazakhstan).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/cache/kazakhstan.osm.pbf"
LEGACY="$HERE/../../maps/build/kazakhstan.osm.pbf"
PBF_URL="${PBF_URL:-https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf}"

mkdir -p "$HERE/cache"

if [ -s "$OUT" ] && [ "${REFRESH:-0}" != "1" ]; then
  echo ">> using existing $OUT (REFRESH=1 to re-download)"
  exit 0
fi

if [ "${REFRESH:-0}" != "1" ] && [ -s "$LEGACY" ]; then
  echo ">> reusing $LEGACY"
  rm -f "$OUT"
  ln "$LEGACY" "$OUT" 2>/dev/null || cp "$LEGACY" "$OUT"
  exit 0
fi

echo ">> downloading $PBF_URL"
curl -fL --retry 3 -C - -o "$OUT.part" "$PBF_URL"
mv "$OUT.part" "$OUT"
