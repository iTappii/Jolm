-- Shared rate limits (Ш-51, review Ш-30 №1): one row per counted request, so several API
-- processes (and instances) enforce ONE limit instead of limit x processes.
--
-- Sliding window: a request is allowed while fewer than `limit` rows of its key are younger than
-- the window. app/ratelimit.py takes a transaction-scoped advisory lock per key, so
-- count-then-insert is atomic across processes. `key_hash` = sha256 of "<rule>:<subject>"
-- (subject = IP, install id or user id): no raw IPs or ids are stored. Nothing about WHAT the
-- request was is stored (guest chat content is still never written, SSOT §3.1).
-- `expires_at` = hit_at + the rule's window; the worker job `retention.cleanup` deletes expired
-- rows hourly (rows past their window never count, so a late cleanup is harmless).
CREATE TABLE rate_limit_hits (
    id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key_hash   text        NOT NULL,
    hit_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX rate_limit_hits_key_idx ON rate_limit_hits (key_hash, hit_at DESC);
CREATE INDEX rate_limit_hits_expires_idx ON rate_limit_hits (expires_at);
