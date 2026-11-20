-- 0003_admins: admin panel accounts (TECH_PLAN Ш-10). Separate from end users (SSOT §3).

CREATE TABLE admins (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email         citext      NOT NULL UNIQUE,
    -- argon2id encoded hash (includes salt and parameters)
    password_hash text        NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    disabled_at   timestamptz
);

-- Only the sha256 of the random cookie token is stored: a DB leak does not yield usable sessions.
CREATE TABLE admin_sessions (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id   uuid        NOT NULL REFERENCES admins (id) ON DELETE CASCADE,
    token_hash text        NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);
CREATE INDEX admin_sessions_admin_idx ON admin_sessions (admin_id);

-- Failed logins only; used for rate limiting per (email, ip) and per ip.
CREATE TABLE admin_login_attempts (
    id           bigserial   PRIMARY KEY,
    email        citext      NOT NULL,
    ip           text        NOT NULL,
    attempted_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX admin_login_attempts_email_ip_idx ON admin_login_attempts (email, ip, attempted_at);
CREATE INDEX admin_login_attempts_ip_idx ON admin_login_attempts (ip, attempted_at);
