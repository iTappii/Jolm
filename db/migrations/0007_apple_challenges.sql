CREATE TABLE apple_consumed_challenges (
    nonce_hash text PRIMARY KEY,
    expires_at timestamptz NOT NULL
);
CREATE INDEX apple_consumed_challenges_expiry ON apple_consumed_challenges(expires_at);
