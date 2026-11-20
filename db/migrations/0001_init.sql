-- 0001_init: extensions and the job queue (TECH_PLAN Ш-03, §3: queue lives in Postgres).

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE jobs (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    kind        text        NOT NULL,
    payload     jsonb       NOT NULL DEFAULT '{}'::jsonb,
    run_at      timestamptz NOT NULL DEFAULT now(),
    attempts    integer     NOT NULL DEFAULT 0,
    locked_at   timestamptz,
    done_at     timestamptz,
    error       text,
    -- idempotent enqueue (periodic schedules): at most one job per non-null key
    dedupe_key  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- pending jobs ordered by due time (worker polls this)
CREATE INDEX jobs_pending_idx ON jobs (run_at) WHERE done_at IS NULL;
CREATE INDEX jobs_done_at_idx ON jobs (done_at) WHERE done_at IS NOT NULL;
CREATE UNIQUE INDEX jobs_dedupe_key_uidx ON jobs (dedupe_key) WHERE dedupe_key IS NOT NULL;
