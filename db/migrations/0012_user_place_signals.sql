-- Memory signals of the trip edits (Ш-38; SSOT §8): a person removed a place from their route
-- or replaced it with another one. Ш-41 reads these rows to show places of that category less
-- often (never to exclude them).
--
-- Personal data: rows hang off users with ON DELETE CASCADE (DELETE /v1/me removes them).
-- `place_id` deliberately has NO ON DELETE CASCADE: the OSM importer merges duplicate places with
-- data/osm/merge.py `merge_place`, which re-points these rows (TECH_PLAN rule 8).
-- `category_slug` is a snapshot of the place's category at the time of the edit (the place's
-- category may change later; the signal is about what the person turned down).
-- `trip_id` is informational: the signal outlives the trip (ON DELETE SET NULL).

CREATE TABLE user_place_signals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    place_id uuid NOT NULL REFERENCES places,
    category_slug text,
    signal text NOT NULL CHECK (signal IN ('removed', 'replaced')),
    trip_id uuid REFERENCES trips ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX user_place_signals_user ON user_place_signals (user_id, created_at DESC);
CREATE INDEX user_place_signals_place ON user_place_signals (place_id);
