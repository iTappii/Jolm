-- 0002_places: place catalogue (TECH_PLAN Ш-07, §5). Money = bigint *_kzt (OPEN(SSOT §16.2): KZT only).

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE place_categories (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    slug       text        NOT NULL UNIQUE,
    parent_id  uuid        REFERENCES place_categories (id) ON DELETE SET NULL,
    name_ru    text        NOT NULL,
    name_en    text        NOT NULL,
    -- outdoor categories suffer from bad weather (SSOT §7.1)
    outdoor    boolean     NOT NULL DEFAULT false,
    sort_order integer     NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE places (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- link to the OpenStreetMap object; NULL for manually created places
    osm_type            text        CHECK (osm_type IN ('node', 'way', 'relation')),
    osm_id              bigint,
    kind                text        NOT NULL DEFAULT 'venue'
                        CHECK (kind IN ('landmark', 'venue', 'nature', 'accommodation', 'event_venue')),
    category_id         uuid        REFERENCES place_categories (id),
    name_ru             text,
    name_en             text,
    name_kk             text,
    description_ru      text,
    description_en      text,
    geom                geography(Point, 4326) NOT NULL,
    address_ru          text,
    address_en          text,
    website             text,
    -- state/public places and sights are never advertising (SSOT §12)
    is_public           boolean     NOT NULL DEFAULT false,
    is_partner          boolean     NOT NULL DEFAULT false,
    is_mountain         boolean     NOT NULL DEFAULT false,
    elevation_m         integer,
    setting             text        CHECK (setting IN ('indoor', 'outdoor', 'mixed')),
    typical_visit_min   integer     CHECK (typical_visit_min > 0),
    entry_price_kzt     bigint      CHECK (entry_price_kzt >= 0),
    avg_check_kzt       bigint      CHECK (avg_check_kzt >= 0),
    price_per_night_kzt bigint      CHECK (price_per_night_kzt >= 0),
    popularity          integer     NOT NULL DEFAULT 0,
    status              text        NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'hidden', 'closed')),
    -- field names set by hand (curated import / admin); OSM re-import must not overwrite them
    manual_override     jsonb       NOT NULL DEFAULT '[]'::jsonb
                        CHECK (jsonb_typeof(manual_override) = 'array'),
    data_updated_at     timestamptz NOT NULL DEFAULT now(),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT places_osm_pair CHECK ((osm_type IS NULL) = (osm_id IS NULL)),
    CONSTRAINT places_has_name CHECK (
        name_ru IS NOT NULL OR name_en IS NOT NULL OR name_kk IS NOT NULL
    ),
    CONSTRAINT places_osm_uniq UNIQUE (osm_type, osm_id)
);

CREATE INDEX places_geom_gix ON places USING gist (geom);
CREATE INDEX places_status_idx ON places (status);
CREATE INDEX places_category_idx ON places (category_id);
-- fuzzy search by name (TECH_PLAN Ш-17)
CREATE INDEX places_name_ru_trgm ON places USING gin (name_ru gin_trgm_ops);
CREATE INDEX places_name_en_trgm ON places USING gin (name_en gin_trgm_ops);

-- weekday: 0 = Monday .. 6 = Sunday. closes <= opens means the interval runs past midnight.
-- Round-the-clock = 00:00-23:59. Several intervals per day are allowed (lunch break).
CREATE TABLE place_hours (
    id       uuid     PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id uuid     NOT NULL REFERENCES places (id) ON DELETE CASCADE,
    weekday  smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    opens    time     NOT NULL,
    closes   time     NOT NULL
);
CREATE INDEX place_hours_place_idx ON place_hours (place_id, weekday);

CREATE TABLE place_photos (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id       uuid        NOT NULL REFERENCES places (id) ON DELETE CASCADE,
    storage_key    text        NOT NULL,
    source         text        NOT NULL DEFAULT 'team'
                   CHECK (source IN ('team', 'user', 'partner', 'osm')),
    author_user_id uuid,
    status         text        NOT NULL DEFAULT 'approved'
                   CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX place_photos_place_idx ON place_photos (place_id);

CREATE TABLE place_menu (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id   uuid        NOT NULL UNIQUE REFERENCES places (id) ON DELETE CASCADE,
    payload    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    source     text        NOT NULL DEFAULT 'team',
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- OPEN(SSOT §16.1): hand-made by the team until the owner decides who builds guest routes
CREATE TABLE curated_routes (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    title_ru       text        NOT NULL,
    title_en       text        NOT NULL,
    description_ru text,
    description_en text,
    status         text        NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE curated_route_items (
    id       uuid     PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id uuid     NOT NULL REFERENCES curated_routes (id) ON DELETE CASCADE,
    place_id uuid     NOT NULL REFERENCES places (id) ON DELETE CASCADE,
    ord      smallint NOT NULL,
    UNIQUE (route_id, ord)
);

-- OPEN(SSOT §16.9): is_promoted drives the "Ad" label on the card
CREATE TABLE events (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id    uuid        REFERENCES places (id) ON DELETE SET NULL,
    title_ru    text        NOT NULL,
    title_en    text,
    starts_at   timestamptz NOT NULL,
    ends_at     timestamptz,
    price_kzt   bigint      CHECK (price_kzt >= 0),
    category_id uuid        REFERENCES place_categories (id),
    is_promoted boolean     NOT NULL DEFAULT false,
    sponsor     text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at IS NULL OR ends_at >= starts_at)
);
CREATE INDEX events_starts_idx ON events (starts_at);
