-- Bonuses for approved user content (Ш-46, SSOT §10.3). 1 bonus ~ 1 tenge. Spending: not built.
--
-- Personal data. `bonus_ledger` is INSERT-ONLY (a trigger refuses UPDATE and DELETE) with one
-- exception: rows go together with the account (user_id ON DELETE CASCADE): the ledger is a
-- personal record, nothing can be spent yet, and published content stays anonymized anyway
-- (submissions.user_id SET NULL, 0018). When spending appears, accounting needs may justify
-- keeping an anonymized row: that is a later decision (OPEN(SSOT §16.8)).
-- No place_id on purpose (TECH_PLAN rule 8): the formula inputs are kept as numbers only.
CREATE TABLE bonus_ledger (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL REFERENCES users ON DELETE CASCADE,
    kind            text        NOT NULL DEFAULT 'accrual' CHECK (kind IN ('accrual')),
    amount          integer     NOT NULL CHECK (amount > 0),
    -- 'submission:<uuid>': one accrual per approved submission, whatever calls the accrual
    idempotency_key text        NOT NULL UNIQUE,
    submission_id   uuid        REFERENCES submissions ON DELETE SET NULL,
    submission_type text        NOT NULL,
    -- the formula inputs (base, factors, field age, trips): audit, no ids
    details         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX bonus_ledger_user_created ON bonus_ledger (user_id, created_at DESC, id DESC);

-- UPDATE is never allowed. DELETE is allowed only when the owner is already gone (account
-- deletion cascades: the user row is no longer visible inside the cascade).
CREATE FUNCTION bonus_ledger_insert_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND NOT EXISTS (SELECT 1 FROM users WHERE id = OLD.user_id) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'bonus_ledger is insert-only';
END
$$;
CREATE TRIGGER bonus_ledger_insert_only BEFORE UPDATE OR DELETE ON bonus_ledger
    FOR EACH ROW EXECUTE FUNCTION bonus_ledger_insert_only();

-- Constants of the TEMPORARY bonus formula (server/app/submissions/bonus_policy.py), edited in the
-- admin panel. OPEN(SSOT §16.8): the real formula and conditions are not decided; app code falls
-- back to bonus_policy.DEFAULTS for a missing key.
CREATE TABLE demand_coefficients (
    key        text          PRIMARY KEY,
    value      numeric(10,3) NOT NULL CHECK (value >= 0),
    updated_at timestamptz   NOT NULL DEFAULT now(),
    updated_by uuid          REFERENCES admins ON DELETE SET NULL
);
INSERT INTO demand_coefficients (key, value) VALUES
    ('base_review', 20), ('base_photo', 50), ('base_menu', 100), ('base_price', 40),
    ('base_transit', 60),
    ('age_full_days', 180), ('age_min', 0.5), ('age_max', 2),
    ('freq_window_days', 90), ('freq_full_trips', 20), ('freq_min', 1), ('freq_max', 2);
