-- Own address / building data for reverse geocoding (Ш-23c, SSOT §6.1, §13).
--
-- Filled by data/osm/import_addresses.py from the shared OSM extract (ODbL, (c) OpenStreetMap
-- contributors): objects with addr:housenumber, and named buildings. A point per object (a way is
-- reduced to the centroid of its nodes). It is reference data, not user data, and carries no
-- place_id, so TECH_PLAN rule 8 (merge_place) does not apply. The import replaces the table
-- content by key (osm_type, osm_id) and deletes rows that vanished from the extract.
CREATE TABLE osm_addresses (
    osm_type    text             NOT NULL CHECK (osm_type IN ('node', 'way')),
    osm_id      bigint           NOT NULL,
    geom        geography(Point, 4326) NOT NULL,
    housenumber text,
    street_ru   text,
    street_en   text,
    street_kk   text,
    name_ru     text,
    name_en     text,
    name_kk     text,
    building    text,
    PRIMARY KEY (osm_type, osm_id),
    CHECK (housenumber IS NOT NULL OR coalesce(name_ru, name_en, name_kk) IS NOT NULL)
);
CREATE INDEX osm_addresses_geom_gix ON osm_addresses USING gist (geom);
