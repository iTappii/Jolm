-- User content (Ш-44, SSOT §10): uploads and submissions.
--
-- Personal data. `uploads` hang off users with ON DELETE CASCADE. `submissions.user_id` is
-- ON DELETE SET NULL: published content (reviews, photos, ...) survives account deletion
-- anonymized, like place_photos.author_user_id (0008); the application deletes the person's
-- UNPUBLISHED submissions explicitly (app/auth/accounts.py).
-- `submissions.place_id` has NO ON DELETE CASCADE: data/osm/merge.py `merge_place` re-points it
-- (TECH_PLAN rule 8). There is deliberately no unique index "one review per user and place": a
-- merge of two places could violate it; the API enforces it instead.

-- A presigned upload slot. status: pending (URL issued) -> used (attached to a submission) |
-- rejected (not an image / wrong size). The object itself lives in the bucket under storage_key.
CREATE TABLE uploads (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid        NOT NULL REFERENCES users ON DELETE CASCADE,
    storage_key  text        NOT NULL UNIQUE,
    content_type text        NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
    size_bytes   integer     NOT NULL CHECK (size_bytes > 0),
    status       text        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'used', 'rejected')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL
);
CREATE INDEX uploads_user_created ON uploads (user_id, created_at DESC);

-- status: pending_filter (transient) | rejected_auto (auto-filter) | published_pending_review
-- (passed the filter, visible, "will be checked later") | approved | rejected (moderator).
-- payload: validated per type (app/submissions/schemas.py); photo types carry `photo_key`.
-- place_id is NULL only for transit data that is not about one place.
CREATE TABLE submissions (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid        REFERENCES users ON DELETE SET NULL,
    place_id       uuid        REFERENCES places,
    type           text        NOT NULL CHECK (type IN ('review', 'menu', 'photo', 'transit', 'price')),
    payload        jsonb       NOT NULL,
    status         text        NOT NULL DEFAULT 'pending_filter'
                   CHECK (status IN ('pending_filter', 'rejected_auto', 'published_pending_review',
                                     'approved', 'rejected')),
    filter_result  jsonb,
    content_hash   text,
    place_photo_id uuid        REFERENCES place_photos ON DELETE SET NULL,
    locale         text        NOT NULL DEFAULT 'en' CHECK (locale IN ('ru', 'en')),
    moderator_id   uuid        REFERENCES admins ON DELETE SET NULL,
    decided_at     timestamptz,
    created_at     timestamptz NOT NULL DEFAULT clock_timestamp(),  -- list order = arrival order
    CHECK (type = 'transit' OR place_id IS NOT NULL)
);
CREATE INDEX submissions_place_published ON submissions (place_id, type, created_at DESC, id DESC);
CREATE INDEX submissions_user_created ON submissions (user_id, created_at DESC, id DESC);
CREATE INDEX submissions_queue ON submissions (created_at, id) WHERE status = 'published_pending_review';
CREATE INDEX submissions_content_hash ON submissions (content_hash) WHERE content_hash IS NOT NULL;
