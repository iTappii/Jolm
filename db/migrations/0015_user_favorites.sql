-- Favourite places (Ш-23b, SSOT §11.5): a person's saved places, shown in the profile and used
-- as a small bonus when planning (Ш-33).
--
-- Personal data: rows hang off users with ON DELETE CASCADE (DELETE /v1/me removes them).
-- `place_id` deliberately has NO ON DELETE CASCADE: data/osm/merge.py `merge_place` re-points
-- these rows when the importer merges duplicate places (TECH_PLAN rule 8); if the person had
-- both places, the duplicate favourite is dropped. A place that goes hidden/closed stays in the
-- table but is not listed. The per-user cap (500) is enforced by the API, not the schema.
CREATE TABLE user_favorites (
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    place_id uuid NOT NULL REFERENCES places,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, place_id)
);
CREATE INDEX user_favorites_place ON user_favorites (place_id);
CREATE INDEX user_favorites_user_created ON user_favorites (user_id, created_at DESC);
