-- Ш-61: the trip planner for the whole country (SSOT §5.4 п. 1-4, 6).
-- OPEN: the numbers of the planner live in `country_planner_settings` (seeded by
-- data/seed/country_planner.sql), never in the code. Without them the planner stays city-only.

CREATE TABLE country_planner_settings (
    key    text PRIMARY KEY,
    value  numeric NOT NULL,
    unit   text NOT NULL,
    source text NOT NULL CHECK (length(btrim(source)) > 0),
    as_of  date NOT NULL
);

-- The brief gets two optional lists (backward compatible: empty by default).
--   dated_wishes: [{"wish": "Чарынский каньон", "date": "2026-12-03"}]  a wish tied to a day: never moved
--   stay_wishes:  [{"wish": "Кольсай", "stay": "day" | "overnight"}]    the person says how
ALTER TABLE trip_briefs
    ADD COLUMN dated_wishes jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(dated_wishes) = 'array'),
    ADD COLUMN stay_wishes  jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(stay_wishes) = 'array');

-- Per-day facts of the plan: {"YYYY-MM-DD": {"kind": "regular" | "transfer", "overnight": {...} | null}}.
-- NULL on trips built before Ш-61 (every day is then "regular", overnight unknown = null).
ALTER TABLE trips ADD COLUMN day_meta jsonb CHECK (day_meta IS NULL OR jsonb_typeof(day_meta) = 'object');

-- A leg that is a move between cities or a long road: {"mode", "from_city", "to_city", "approximate",
-- "price_kzt_min", "price_kzt_max"}. NULL for ordinary legs.
ALTER TABLE trip_legs ADD COLUMN intercity jsonb CHECK (intercity IS NULL OR jsonb_typeof(intercity) = 'object');

-- Lodging options of one overnight point: 0 = the home city (as before), 1.. = the other points
-- in the order of the trip (their cities and nights are in the stored budget, lodging.stays).
ALTER TABLE trip_lodging_options ADD COLUMN stay smallint NOT NULL DEFAULT 0 CHECK (stay >= 0);
