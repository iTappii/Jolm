-- 0004_transit: public transport network (TECH_PLAN Ш-21, §5): stops, routes, ordered stops of a route.
-- Source: OpenStreetMap route relations (metro/bus/trolleybus/tram) + data/seed/transit_manual.csv.
-- Merge rule (TECH_PLAN §0 rule 8) does not apply: nothing here references `places`.

CREATE TABLE transit_stops (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    geom            geography(Point, 4326) NOT NULL,
    name_ru         text,
    name_en         text,
    name_kk         text,
    kind            text        NOT NULL CHECK (kind IN ('bus', 'metro', 'trolleybus', 'tram')),
    -- OSM object; NULL for stops added by hand (NULLs never collide in the unique index)
    osm_type        text        CHECK (osm_type IN ('node', 'way')),
    osm_id          bigint,
    -- field names edited by hand that the OSM import must not overwrite
    manual_override jsonb       NOT NULL DEFAULT '[]'::jsonb
                    CHECK (jsonb_typeof(manual_override) = 'array'),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (osm_type, osm_id)
);
CREATE INDEX transit_stops_geom_idx ON transit_stops USING gist (geom);

CREATE TABLE transit_routes (
    id               uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    kind             text         NOT NULL CHECK (kind IN ('bus', 'metro', 'trolleybus', 'tram')),
    ref              text,
    name_ru          text,
    name_en          text,
    -- approximate: no official timetable/GTFS for Almaty; defaults come from the manual seed
    avg_headway_min  numeric(5, 1) NOT NULL CHECK (avg_headway_min > 0),
    speed_kmh        numeric(4, 1) NOT NULL CHECK (speed_kmh > 0),
    -- one OSM route relation = one direction (or one loop); NULL for hand-made routes
    osm_relation_id  bigint       UNIQUE,
    manual_override  jsonb        NOT NULL DEFAULT '[]'::jsonb
                     CHECK (jsonb_typeof(manual_override) = 'array'),
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE transit_route_stops (
    route_id uuid    NOT NULL REFERENCES transit_routes (id) ON DELETE CASCADE,
    stop_id  uuid    NOT NULL REFERENCES transit_stops (id) ON DELETE RESTRICT,
    ord      integer NOT NULL CHECK (ord >= 0),
    PRIMARY KEY (route_id, stop_id, ord),
    UNIQUE (route_id, ord)
);
CREATE INDEX transit_route_stops_stop_idx ON transit_route_stops (stop_id);
