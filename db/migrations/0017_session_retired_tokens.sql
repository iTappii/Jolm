-- Refresh-token reuse detection (Ш-43, review Ш-24 №1).
--
-- A session row is the token family: one sign-in = one session, every refresh replaces the
-- current hash in `sessions.refresh_token_hash`. The replaced (retired) hashes are kept here so
-- that presenting an already-rotated token can be told apart from a random invalid one; reuse
-- after the short grace window revokes the whole session (see app/auth/sessions.py).
--
-- Personal-data table: hangs off sessions (which cascade from users), so account deletion and
-- session removal clean it up. No place_id (TECH_PLAN rule 8 does not apply).
CREATE TABLE session_retired_tokens (
    token_hash text        PRIMARY KEY,
    session_id uuid        NOT NULL REFERENCES sessions ON DELETE CASCADE,
    retired_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX session_retired_tokens_session ON session_retired_tokens (session_id, retired_at);
