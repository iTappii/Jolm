-- Ш-57: regions (SSOT §1, §5.4). The data and the code are built around a region (boundary, time zone,
-- currency, languages, map centre and camera), not around one city. Almaty is the first region with the values
-- the code used to hard-code (planner/area.py: bounding box and centre; Asia/Almaty; KZT; ru + en).
-- The boundary is the old rectangle of the planner area (the city, Medeu/Shymbulak, Kok-Zhailau, Big Almaty Lake
-- and Talgar's edge); when real polygons come (Ш-58), only this column changes.
-- Keep server/app/regions/seed.py in step with this row (a test compares them).
CREATE TABLE regions (
    id           text PRIMARY KEY CHECK (id ~ '^[a-z][a-z0-9_-]*$'),
    name_ru      text NOT NULL,
    name_en      text NOT NULL,
    boundary     geometry(Polygon, 4326) NOT NULL,
    timezone     text NOT NULL,
    currency     text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    languages    text[] NOT NULL CHECK (cardinality(languages) >= 1),
    centre_lat   double precision NOT NULL CHECK (centre_lat BETWEEN -90 AND 90),
    centre_lon   double precision NOT NULL CHECK (centre_lon BETWEEN -180 AND 180),
    camera_zoom  double precision NOT NULL CHECK (camera_zoom BETWEEN 0 AND 22),
    is_default   boolean NOT NULL DEFAULT false
);
CREATE INDEX regions_boundary ON regions USING gist (boundary);
-- exactly one default region
CREATE UNIQUE INDEX regions_one_default ON regions (is_default) WHERE is_default;

INSERT INTO regions (id, name_ru, name_en, boundary, timezone, currency, languages,
                     centre_lat, centre_lon, camera_zoom, is_default)
VALUES ('almaty', 'Алматы', 'Almaty', ST_MakeEnvelope(76.70, 42.95, 77.30, 43.45, 4326),
        'Asia/Almaty', 'KZT', ARRAY['ru', 'en'], 43.2389, 76.9455, 11, true);
