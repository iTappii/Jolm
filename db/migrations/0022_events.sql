-- Events for tourists (Ш-48, SSOT §5.1, §12): the table exists since 0002; this adds a free
-- description and own coordinates for events that are not at a place of the database.
--
-- `sponsor` is the organizer. Where: `place_id` (coordinates come from the place) or `geom`.
-- `place_id` stays ON DELETE SET NULL (an event outlives a deleted place only with its `geom`);
-- `merge_place` re-points it (0002 era, TECH_PLAN rule 8).
-- Ads (SSOT §12): attractions and state places (`places.is_public`) never get ads. The trigger
-- below refuses `is_promoted` on such a place; the API also shows the ad label only when the
-- place is not public (a place can become public later).
ALTER TABLE events
    ADD COLUMN description_ru text,
    ADD COLUMN description_en text,
    ADD COLUMN geom geography(Point, 4326);
CREATE INDEX events_geom_idx ON events USING gist (geom);
CREATE INDEX events_place_idx ON events (place_id);

CREATE FUNCTION events_no_public_ads() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.is_promoted AND NEW.place_id IS NOT NULL
       AND EXISTS (SELECT 1 FROM places WHERE id = NEW.place_id AND is_public) THEN
        RAISE EXCEPTION 'events at public places cannot be promoted' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER events_no_public_ads BEFORE INSERT OR UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION events_no_public_ads();
