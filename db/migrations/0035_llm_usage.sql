-- Daily model-token counters (Ш-66): one row per (day of the default region, key). Keys are
-- sha256("<scope>:<subject>") like rate_limit_hits, so no raw user id, install id or IP is stored;
-- scopes: user, guest_install, guest_ip and the single "global" key for the whole service.
-- `tokens` = input + output tokens reported by the model provider (TurnRecord.usage).
-- Rows older than a few days are deleted by the worker (`retention.cleanup`).
CREATE TABLE llm_usage_daily (
    day      date   NOT NULL,
    key_hash text   NOT NULL,
    tokens   bigint NOT NULL DEFAULT 0 CHECK (tokens >= 0),
    PRIMARY KEY (day, key_hash)
);
