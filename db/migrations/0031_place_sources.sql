-- Ш-58: where each place field comes from (SSOT §13, §2.4) and external ids of the open datasets.
--
-- place_field_sources: for the fields that open data fills (names, address, website, phone, category,
-- coordinates, opening hours) one row says which source set the current value:
--   manual / partner  - team edit in the admin, or the venue itself;
--   user              - approved user content (Ш-44);
--   osm / overture / foursquare - open data.
-- Priority (source_rank): manual = partner > user > osm > overture > foursquare. A monthly import
-- changes only fields whose source is an open one of the same or lower rank; manual / partner / user
-- fields are never overwritten. `places.manual_override` stays as before and means "manual" for the
-- fields it lists (the importers check both).
CREATE FUNCTION source_rank(source text) RETURNS integer
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE source
        WHEN 'manual' THEN 5 WHEN 'partner' THEN 5 WHEN 'user' THEN 4
        WHEN 'osm' THEN 3 WHEN 'overture' THEN 2 WHEN 'foursquare' THEN 1 ELSE 0 END
$$;

ALTER TABLE places ADD COLUMN phone text;

CREATE TABLE place_field_sources (
    place_id   uuid        NOT NULL REFERENCES places (id) ON DELETE CASCADE,
    field      text        NOT NULL CHECK (field ~ '^[a-z][a-z0-9_]*$'),
    source     text        NOT NULL
               CHECK (source IN ('manual', 'partner', 'user', 'osm', 'overture', 'foursquare')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (place_id, field)
);

-- Ids of a place in the open datasets (OSM keeps places.osm_type / osm_id), so a repeated import
-- finds the same place instead of making a new one.
CREATE TABLE place_external_ids (
    source      text        NOT NULL CHECK (source IN ('overture', 'foursquare')),
    external_id text        NOT NULL,
    place_id    uuid        NOT NULL REFERENCES places (id) ON DELETE CASCADE,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, external_id)
);
CREATE INDEX place_external_ids_place_idx ON place_external_ids (place_id);

-- Backfill: fields in manual_override are manual; the rest of a place that came from OSM is osm; a
-- place without an OSM object was made by hand.
INSERT INTO place_field_sources (place_id, field, source)
SELECT p.id, f.field,
       CASE WHEN p.manual_override @> to_jsonb(f.field) THEN 'manual'
            WHEN p.osm_id IS NOT NULL THEN 'osm'
            ELSE 'manual' END
FROM places p
CROSS JOIN LATERAL (VALUES
    ('name_ru', p.name_ru IS NOT NULL),
    ('name_en', p.name_en IS NOT NULL),
    ('name_kk', p.name_kk IS NOT NULL),
    ('address_ru', p.address_ru IS NOT NULL),
    ('address_en', p.address_en IS NOT NULL),
    ('website', p.website IS NOT NULL),
    ('category_id', p.category_id IS NOT NULL),
    ('geom', true),
    ('hours', EXISTS (SELECT 1 FROM place_hours h WHERE h.place_id = p.id))
) AS f(field, present)
WHERE f.present OR p.manual_override @> to_jsonb(f.field);
