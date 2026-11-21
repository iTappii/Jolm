-- Live plan (Ш-40, SSOT §7.1-7.2): weather change proposals, push outbox, mountain notices.
--
-- trip_change_proposals: the engine's suggestion after a forecast re-check. Applied only after
-- the person accepts (TECH_PLAN §2, working default of SSOT §16.4). Everything hangs off users
-- and trips with ON DELETE CASCADE (account deletion removes it). The places a proposal
-- mentions are real columns WITHOUT cascade (rule 8: data/osm/merge.py `merge_place` re-points
-- them); `diff` holds only numbers (problem kind, hours, peak value), never place ids.
--   kind 'move_day': the stop (place_id) goes from `day` to `to_day` of the same trip;
--   kind 'replace' : the stop (place_id) is replaced by `target_place_id` on the same day.
-- `trip_version` is the version of the plan the proposal was computed for: a different version
-- means the plan changed since, the proposal is stale ('expired', accept -> 409).
-- At most one pending proposal per trip (partial unique index): the next one comes after a
-- decision, so proposals never conflict with each other.
CREATE TABLE trip_change_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    trip_id uuid NOT NULL REFERENCES trips ON DELETE CASCADE,
    reason text NOT NULL CHECK (reason IN ('weather', 'mountain')),
    kind text NOT NULL CHECK (kind IN ('move_day', 'replace')),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    trip_version integer NOT NULL,
    day date NOT NULL,
    to_day date,
    item_id uuid,  -- trip_items.id when proposed; no FK (items are re-created by rebuilds)
    place_id uuid NOT NULL REFERENCES places,
    target_place_id uuid REFERENCES places,
    diff jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    CHECK ((kind = 'move_day' AND to_day IS NOT NULL AND target_place_id IS NULL)
        OR (kind = 'replace' AND to_day IS NULL AND target_place_id IS NOT NULL))
);
CREATE UNIQUE INDEX trip_change_proposals_one_pending
    ON trip_change_proposals (trip_id) WHERE status = 'pending';
CREATE INDEX trip_change_proposals_trip ON trip_change_proposals (trip_id, created_at DESC);
CREATE INDEX trip_change_proposals_user ON trip_change_proposals (user_id);
CREATE INDEX trip_change_proposals_place ON trip_change_proposals (place_id);
CREATE INDEX trip_change_proposals_target ON trip_change_proposals (target_place_id)
    WHERE target_place_id IS NOT NULL;

-- A chat message that carries a proposal (the app shows accept / decline under it).
ALTER TABLE chat_messages
    ADD COLUMN proposal_id uuid REFERENCES trip_change_proposals ON DELETE SET NULL;

-- One mountain-morning message per trip day (SSOT §7.2): the row is the idempotency record.
CREATE TABLE trip_day_notices (
    trip_id uuid NOT NULL REFERENCES trips ON DELETE CASCADE,
    day date NOT NULL,
    kind text NOT NULL CHECK (kind IN ('mountain')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (trip_id, day, kind)
);

-- Push outbox. The row is written in the same transaction as the chat message and the proposal;
-- the `push.send` job delivers it outside any transaction. `delivered_to` lists the devices
-- already served, so a retry never repeats a push to them; `sent_at` closes the notification.
-- `data` carries ids of trips / proposals / chats only (no place ids, rule 8 does not apply).
CREATE TABLE push_notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    kind text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    data jsonb NOT NULL DEFAULT '{}',
    dedupe_key text UNIQUE,
    delivered_to uuid[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);
CREATE INDEX push_notifications_user ON push_notifications (user_id);
CREATE INDEX devices_user ON devices (user_id) WHERE user_id IS NOT NULL;
