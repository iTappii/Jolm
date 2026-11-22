-- Ш-54: the live route drawn on the map while the tourist is still chatting (SSOT §11.1).
-- One stop per must-have wish that found a place, in wish order (`ord` 1..n); the best match is the stop,
-- the next best are its alternatives. The leg_* columns hold the leg from the PREVIOUS stop to this one
-- (NULL for the first stop, or when no route could be computed). Rewritten whole on every change.
-- place_id references places without ON DELETE CASCADE (TECH_PLAN rule 8: data/osm/merge.py moves them);
-- the rows hang off chats, so deleting a user (or a chat) removes them.
CREATE TABLE chat_live_stops (
    chat_id uuid NOT NULL REFERENCES chats ON DELETE CASCADE,
    ord integer NOT NULL CHECK (ord >= 1),
    wish text NOT NULL,
    place_id uuid NOT NULL REFERENCES places,
    leg_mode text CHECK (leg_mode IN ('walk', 'transit', 'car')),
    leg_duration_s integer CHECK (leg_duration_s >= 0),
    leg_distance_m integer CHECK (leg_distance_m >= 0),
    PRIMARY KEY (chat_id, ord)
);
CREATE INDEX chat_live_stops_place ON chat_live_stops (place_id);

CREATE TABLE chat_live_alternatives (
    chat_id uuid NOT NULL REFERENCES chats ON DELETE CASCADE,
    ord integer NOT NULL CHECK (ord >= 1),
    place_id uuid NOT NULL REFERENCES places,
    rank smallint NOT NULL,
    PRIMARY KEY (chat_id, ord, place_id)
);
CREATE INDEX chat_live_alternatives_place ON chat_live_alternatives (place_id);
