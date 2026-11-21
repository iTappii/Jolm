-- Analytics (Ш-50, SSOT §12 stage 1): product events and the metric "a tourist really came".
--
-- `analytics_events`: install/launch, sign-in, route created, place shown in a route, directions
-- started, route downloaded. Client events (app_install, app_launch, directions_start) arrive at
-- POST /v1/analytics/events; the rest are written by the server where it already knows (sign-in,
-- build_trip, GET /trips/{id}/offline). Event names and property keys are whitelisted in
-- app/analytics/events.py (no CHECK here: a new event must not need a migration).
-- No coordinates, no free text: `props` holds a few whitelisted scalars.
--
-- Personal data: the pseudonymous `install_id` and `user_id` tie events to a person. On account
-- deletion app/auth/accounts.py ANONYMIZES the person's events (user_id and install_id set to NULL
-- for the user's rows and for every other row of the same install); the counts stay. The FK
-- `user_id ON DELETE SET NULL` and `trip_id ON DELETE SET NULL` are the safety net.
-- `place_id` has NO ON DELETE CASCADE: data/osm/merge.py `merge_place` re-points it (TECH_PLAN
-- rule 8).
--
-- "I am here" is NOT duplicated here: check-ins (Ш-47) live in `place_crowd_reports`
-- (kind = 'checkin') and the views below read them (they go with the account, by its cascade).
CREATE TABLE analytics_events (
    id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 40),
    source          text        NOT NULL CHECK (source IN ('client', 'server')),
    -- the id the client gave the event: a retried batch is not counted twice
    client_event_id uuid,
    install_id      uuid,
    user_id         uuid        REFERENCES users ON DELETE SET NULL,
    place_id        uuid        REFERENCES places,
    trip_id         uuid        REFERENCES trips ON DELETE SET NULL,
    props           jsonb       NOT NULL DEFAULT '{}'::jsonb,
    -- when it happened (the client's time corrected by the clock skew) / when the server got it
    occurred_at     timestamptz NOT NULL,
    received_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (install_id, client_event_id)
);
CREATE INDEX analytics_events_name_time ON analytics_events (name, occurred_at);
CREATE INDEX analytics_events_place ON analytics_events (place_id, name, occurred_at)
    WHERE place_id IS NOT NULL;
CREATE INDEX analytics_events_install ON analytics_events (install_id) WHERE install_id IS NOT NULL;
CREATE INDEX analytics_events_user ON analytics_events (user_id) WHERE user_id IS NOT NULL;

-- The metric "a tourist really came": a check-in (the person was within 200 m of the place, Ш-47,
-- location given for that one action, no background tracking) at a place that is in the same
-- person's trip (main plan), inside the item's time window +- 1 hour. One check-in = one visit
-- even if the place is in the trip twice (the earliest item wins). Day = local Asia/Almaty date.
-- The tolerance is a working default (ADR 0003); keep it in sync with
-- VISIT_TOLERANCE in app/analytics/service.py (a test compares them).
CREATE VIEW analytics_visits AS
SELECT DISTINCT ON (r.id)
       r.id AS checkin_id,
       r.user_id,
       r.place_id,
       i.trip_id,
       i.id AS trip_item_id,
       r.created_at AS visited_at,
       (r.created_at AT TIME ZONE 'Asia/Almaty')::date AS day
FROM place_crowd_reports r
JOIN trips t ON t.user_id = r.user_id
JOIN trip_items i ON i.trip_id = t.id AND i.variant = 'main' AND i.place_id = r.place_id
WHERE r.kind = 'checkin'
  AND r.created_at BETWEEN i.starts_at - interval '1 hour' AND i.ends_at + interval '1 hour'
ORDER BY r.id, i.starts_at, i.id;

-- Everything a person did, in one shape for the funnel: events plus check-ins and visits.
-- `person` = the account if known, else the device (a guest). Step 1 of the funnel counts devices
-- (`install_id`), the later steps count accounts: the two are not the same unit.
CREATE VIEW analytics_actions AS
SELECT e.name, COALESCE(e.user_id::text, e.install_id::text) AS person,
       e.user_id, e.install_id, e.place_id, e.occurred_at
FROM analytics_events e
UNION ALL
SELECT 'checkin', r.user_id::text, r.user_id, NULL::uuid, r.place_id, r.created_at
FROM place_crowd_reports r WHERE r.kind = 'checkin'
UNION ALL
SELECT 'visit', v.user_id::text, v.user_id, NULL::uuid, v.place_id, v.visited_at
FROM analytics_visits v;
