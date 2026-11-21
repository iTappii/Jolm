-- Bookings skeleton (Ш-49, SSOT §9; OPEN(SSOT §16.7): partners and payment are not decided).
-- No payment in the app (ADR 0003 п.7): a booking is a request to the partner through an
-- adapter. Only the stub adapter exists.
--
-- `partners`: a partner company and which adapter talks to it. `partner_places`: which places a
-- partner serves and which kinds (table | room | ticket | food); a place has a booking button
-- only when it is linked here. `place_id` has no ON DELETE CASCADE (TECH_PLAN rule 8:
-- `merge_place` re-points the link and the bookings).
-- `bookings` are personal data: `user_id` ON DELETE CASCADE.
CREATE TABLE partners (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text        NOT NULL,
    adapter    text        NOT NULL DEFAULT 'stub',
    config     jsonb       NOT NULL DEFAULT '{}'::jsonb,
    is_active  boolean     NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE partner_places (
    partner_id   uuid   NOT NULL REFERENCES partners ON DELETE CASCADE,
    place_id     uuid   NOT NULL REFERENCES places,
    kinds        text[] NOT NULL CHECK (kinds <> '{}' AND kinds <@ ARRAY['table', 'room', 'ticket', 'food']),
    external_ref text,
    PRIMARY KEY (partner_id, place_id)
);
CREATE INDEX partner_places_place ON partner_places (place_id);

-- status: pending (the partner has not answered) | confirmed | declined | cancelled | failed.
CREATE TABLE bookings (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL REFERENCES users ON DELETE CASCADE,
    place_id        uuid        NOT NULL REFERENCES places,
    partner_id      uuid        NOT NULL REFERENCES partners,
    kind            text        NOT NULL CHECK (kind IN ('table', 'room', 'ticket', 'food')),
    status          text        NOT NULL CHECK (status IN ('pending', 'confirmed', 'declined', 'cancelled', 'failed')),
    payload         jsonb       NOT NULL,
    external_ref    text,
    idempotency_key text,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX bookings_idempotency ON bookings (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX bookings_user_created ON bookings (user_id, created_at DESC, id DESC);
CREATE INDEX bookings_place ON bookings (place_id);
