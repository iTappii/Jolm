CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    locale text NOT NULL DEFAULT 'en' CHECK (locale IN ('ru','en')),
    display_name text,
    deleted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE auth_identities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    provider text NOT NULL CHECK (provider IN ('email','phone','apple')),
    subject text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, subject)
);
CREATE INDEX auth_identities_user ON auth_identities(user_id);
CREATE TABLE devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users ON DELETE CASCADE,
    install_id uuid NOT NULL UNIQUE,
    apns_token text,
    locale text NOT NULL DEFAULT 'en' CHECK (locale IN ('ru','en')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    device_id uuid REFERENCES devices ON DELETE SET NULL,
    refresh_token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user ON sessions(user_id);
CREATE TABLE otp_codes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel text NOT NULL CHECK (channel IN ('email','phone')),
    destination_hash text NOT NULL,
    ip_hash text NOT NULL,
    code_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    attempts smallint NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    consumed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX otp_destination_window ON otp_codes(channel, destination_hash, created_at DESC);
CREATE INDEX otp_ip_window ON otp_codes(ip_hash, created_at DESC);
