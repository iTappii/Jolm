#!/usr/bin/env python3
"""Generates the Jol map styles (OpenMapTiles schema) -> maps/style/*.json.

Run:  python3 maps/style/build_styles.py
Outputs: jol-light.json, jol-dark.json (labels ru-first, default), and
         jol-light.en.json, jol-dark.en.json (labels en-first).
The committed JSON files are generated; edit this file, not the JSON.
"""
import json
from pathlib import Path

OUT = Path(__file__).parent
ACCENT = "#FF7A00"

# Source URL is a placeholder: the app / demo replaces it (see maps/README.md).
# Tile file name (Ш-59: whole country). maps/serve.py falls back to almaty.pmtiles if this file is absent.
PMTILES_NAME = "kazakhstan.pmtiles"
PMTILES_URL = f"pmtiles://https://tiles.example.com/{PMTILES_NAME}"
# TODO(self-host): MapLibre public demo glyph server (Noto Sans, verified to include Cyrillic);
# not for production traffic -> self-host the .pbf glyphs on our bucket before release.
# (fonts.openmaptiles.org now returns HTML, do not use.)
GLYPHS = "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf"
# TODO(sprite): category icon sprite (maps/sprite/jol.{json,png}) not built yet.
# When it exists, add "sprite": "<base>/sprite/jol" and icon-image to the poi layers.

PALETTES = {
    "light": dict(
        bg="#F3F0E9", water="#C9DEE9", waterway="#B3D0DF", wood="#D5E4C8", grass="#E2EAD3",
        park="#DDE9CF", residential="#EDE9E0", cemetery="#DFE5D6", sand="#EFE6CF", ice="#F4F8FA",
        building="#E2DCD0", building_line="#D3CCBE",
        road="#FFFFFF", road_casing="#D9D3C6", minor="#FBF9F5", path="#B9B09F",
        major="#FFE2BF", major_casing="#EBB77B", rail="#B9B3A6",
        boundary="#A99F8E", text="#2B2926", text_halo="#FFFFFF", text_soft="#6E685D",
        water_text="#4F7F98", park_text="#4F7A45", peak="#7A6F5F",
    ),
    "dark": dict(
        bg="#17181B", water="#0F1C26", waterway="#17303F", wood="#1B2519", grass="#1A221A",
        park="#1C2A1D", residential="#1D1E22", cemetery="#1D241E", sand="#25231C", ice="#222A30",
        building="#25262B", building_line="#2E3036",
        road="#33353B", road_casing="#101113", minor="#2A2C31", path="#55575E",
        major="#5A3A18", major_casing="#1A1209", rail="#4A4C52",
        boundary="#6B6A66", text="#ECE8E0", text_halo="#17181B", text_soft="#A39E94",
        water_text="#6C9BB5", park_text="#7FA874", peak="#A39A8A",
    ),
}


def name_expr(lang):
    """Label expression: preferred language -> other language -> local name.
    Both `name:xx` (Planetiler/OSM) and `name_xx` (OpenMapTiles legacy) keys are tried."""
    order = ["ru", "en"] if lang == "ru" else ["en"]
    parts = []
    for l in order:
        parts += [["get", f"name:{l}"], ["get", f"name_{l}"]]
    if lang == "en":
        parts.append(["get", "name:latin"])  # transliteration when no English name exists
    parts.append(["get", "name"])
    return ["coalesce", *parts]


def interp(*stops):
    out = ["interpolate", ["exponential", 1.4], ["zoom"]]
    for z, v in stops:
        out += [z, v]
    return out


def build(theme, lang):
    c = PALETTES[theme]
    nm = name_expr(lang)
    L = []

    def add(**kw):
        L.append(kw)

    sans, bold = ["Noto Sans Regular"], ["Noto Sans Bold"]
    halo = dict(**{"text-halo-color": c["text_halo"], "text-halo-width": 1.4, "text-halo-blur": 0.5})
    road_cls = lambda *cl: ["in", "class", *cl]

    add(id="background", type="background", paint={"background-color": c["bg"]})
    add(id="landcover-ice", type="fill", source="openmaptiles", **{"source-layer": "landcover"},
        filter=["==", "class", "ice"], paint={"fill-color": c["ice"]})
    add(id="landcover-wood", type="fill", source="openmaptiles", **{"source-layer": "landcover"},
        filter=["==", "class", "wood"], paint={"fill-color": c["wood"], "fill-opacity": 0.8})
    add(id="landcover-grass", type="fill", source="openmaptiles", **{"source-layer": "landcover"},
        filter=["in", "class", "grass", "farmland"], paint={"fill-color": c["grass"], "fill-opacity": 0.7})
    add(id="landcover-sand", type="fill", source="openmaptiles", **{"source-layer": "landcover"},
        filter=["==", "class", "sand"], paint={"fill-color": c["sand"]})
    add(id="landuse-residential", type="fill", source="openmaptiles", **{"source-layer": "landuse"},
        filter=["in", "class", "residential", "suburb", "neighbourhood", "commercial", "retail", "industrial"],
        paint={"fill-color": c["residential"], "fill-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.5, 14, 1]})
    add(id="landuse-cemetery", type="fill", source="openmaptiles", **{"source-layer": "landuse"},
        filter=["==", "class", "cemetery"], paint={"fill-color": c["cemetery"]})
    add(id="park", type="fill", source="openmaptiles", **{"source-layer": "park"},
        paint={"fill-color": c["park"], "fill-opacity": 0.85})
    add(id="water", type="fill", source="openmaptiles", **{"source-layer": "water"},
        filter=["!=", "brunnel", "tunnel"], paint={"fill-color": c["water"]})
    add(id="waterway", type="line", source="openmaptiles", **{"source-layer": "waterway"},
        filter=["!=", "brunnel", "tunnel"],
        paint={"line-color": c["waterway"], "line-width": interp((8, 0.4), (14, 1.8), (18, 5))})
    add(id="building", type="fill", source="openmaptiles", **{"source-layer": "building"}, minzoom=14,
        paint={"fill-color": c["building"], "fill-outline-color": c["building_line"]})

    # roads: casing under fill, grouped by class
    groups = [
        ("minor", ("minor", "service", "track"), c["minor"], c["road_casing"], [(12, 0.4), (14, 1.5), (18, 12)], 13),
        ("tertiary", ("tertiary",), c["road"], c["road_casing"], [(11, 0.6), (14, 2.5), (18, 18)], 11),
        ("secondary", ("secondary",), c["road"], c["road_casing"], [(9, 0.6), (14, 3.5), (18, 22)], 9),
        ("primary", ("primary",), c["major"], c["major_casing"], [(8, 0.6), (14, 4.5), (18, 26)], 7),
        ("trunk", ("trunk", "motorway"), c["major"], c["major_casing"], [(5, 0.6), (14, 5), (18, 28)], 5),
    ]
    for gid, cls, fill, casing, widths, minz in groups:
        flt = ["all", road_cls(*cls), ["!=", "brunnel", "tunnel"]]
        add(id=f"road-{gid}-casing", type="line", source="openmaptiles", **{"source-layer": "transportation"},
            minzoom=minz, filter=flt, layout={"line-cap": "round", "line-join": "round"},
            paint={"line-color": casing, "line-width": interp(*[(z, w + (0.6 if z < 14 else 1.5)) for z, w in widths])})
        add(id=f"road-{gid}", type="line", source="openmaptiles", **{"source-layer": "transportation"},
            minzoom=minz, filter=flt, layout={"line-cap": "round", "line-join": "round"},
            paint={"line-color": fill, "line-width": interp(*widths)})
    add(id="road-path", type="line", source="openmaptiles", **{"source-layer": "transportation"}, minzoom=13,
        filter=road_cls("path", "pedestrian"),
        layout={"line-join": "round"},
        paint={"line-color": c["path"], "line-dasharray": [2, 1.5], "line-width": interp((13, 0.5), (18, 2))})
    add(id="rail", type="line", source="openmaptiles", **{"source-layer": "transportation"}, minzoom=10,
        filter=road_cls("rail", "transit"),
        paint={"line-color": c["rail"], "line-width": interp((10, 0.4), (18, 2)), "line-dasharray": [4, 3]})
    add(id="boundary-country", type="line", source="openmaptiles", **{"source-layer": "boundary"},
        filter=["all", ["<=", "admin_level", 4], ["!=", "maritime", 1]],
        paint={"line-color": c["boundary"], "line-dasharray": [3, 2], "line-width": interp((2, 0.6), (10, 1.6))})

    # ---- labels ----
    add(id="water-name", type="symbol", source="openmaptiles", **{"source-layer": "water_name"},
        layout={"text-field": nm, "text-font": ["Noto Sans Regular"], "text-size": 12, "text-letter-spacing": 0.1,
                "symbol-placement": "point"},
        paint={"text-color": c["water_text"], **halo})
    add(id="mountain-peak", type="symbol", source="openmaptiles", **{"source-layer": "mountain_peak"},
        minzoom=9, filter=["has", "name"],
        layout={"text-field": ["format", nm, {}, "\n", {}, ["to-string", ["coalesce", ["get", "ele"], ""]], {"text-size": 9}],
                "text-font": sans, "text-size": 11, "text-anchor": "top", "text-offset": [0, 0.3]},
        paint={"text-color": c["peak"], **halo})
    add(id="road-name", type="symbol", source="openmaptiles", **{"source-layer": "transportation_name"},
        minzoom=13, filter=["in", "class", "motorway", "trunk", "primary", "secondary", "tertiary", "minor"],
        layout={"text-field": nm, "text-font": sans, "text-size": interp((13, 10), (18, 13)),
                "symbol-placement": "line", "text-rotation-alignment": "map"},
        paint={"text-color": c["text_soft"], **halo})
    add(id="poi", type="symbol", source="openmaptiles", **{"source-layer": "poi"}, minzoom=15,
        filter=["<=", "rank", 20],
        # TODO(sprite): icon-image by category once the Jol sprite exists.
        layout={"text-field": nm, "text-font": sans, "text-size": 11, "text-anchor": "top",
                "text-offset": [0, 0.4], "text-max-width": 8},
        paint={"text-color": c["park_text"], **halo})
    place_filters = [
        ("place-city", ["in", "class", "city"], 4, 16, bold),
        ("place-town", ["==", "class", "town"], 7, 15, sans),
        ("place-suburb", ["in", "class", "suburb", "neighbourhood", "quarter"], 11, 13, sans),
        ("place-village", ["in", "class", "village", "hamlet", "isolated_dwelling"], 10, 12, sans),
    ]
    for pid, flt, minz, size, font in place_filters:
        add(id=pid, type="symbol", source="openmaptiles", **{"source-layer": "place"}, minzoom=minz, filter=flt,
            layout={"text-field": nm, "text-font": font,
                    "text-size": interp((minz, size - 3), (minz + 5, size + 2)), "text-max-width": 8},
            paint={"text-color": c["text"], **halo})

    # ---- Jol overlay: route + picked places, fed by the app via setData ----
    add(id="jol-route-casing", type="line", source="jol-route",
        layout={"line-cap": "round", "line-join": "round"},
        paint={"line-color": c["text_halo"], "line-width": interp((8, 5), (16, 11)), "line-opacity": 0.9})
    add(id="jol-route", type="line", source="jol-route",
        layout={"line-cap": "round", "line-join": "round"},
        paint={"line-color": ACCENT, "line-width": interp((8, 3), (16, 7))})
    add(id="jol-places-circle", type="circle", source="jol-places",
        paint={"circle-color": ACCENT, "circle-radius": interp((8, 4), (16, 9)),
               "circle-stroke-color": "#FFFFFF", "circle-stroke-width": 2})
    add(id="jol-places-label", type="symbol", source="jol-places", minzoom=11,
        layout={"text-field": ["coalesce", ["get", "name"], ""], "text-font": bold, "text-size": 12,
                "text-anchor": "top", "text-offset": [0, 0.9], "text-optional": True},
        paint={"text-color": c["text"], **halo})

    empty = {"type": "FeatureCollection", "features": []}
    return {
        "version": 8,
        "name": f"Jol {theme} ({lang})",
        "metadata": {"jol:theme": theme, "jol:label-lang": lang, "jol:accent": ACCENT,
                     "jol:generated-by": "maps/style/build_styles.py"},
        "center": [76.945, 43.238],
        "zoom": 11,
        "glyphs": GLYPHS,
        "sources": {
            "openmaptiles": {
                "type": "vector", "url": PMTILES_URL, "minzoom": 0, "maxzoom": 14,
                "attribution": '<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>',
            },
            "jol-route": {"type": "geojson", "data": empty},
            "jol-places": {"type": "geojson", "data": empty},
        },
        "layers": L,
    }


for theme in PALETTES:
    for lang in ("ru", "en"):
        fn = f"jol-{theme}.json" if lang == "ru" else f"jol-{theme}.{lang}.json"
        (OUT / fn).write_text(json.dumps(build(theme, lang), ensure_ascii=False, indent=2) + "\n")
        print("wrote", fn)
