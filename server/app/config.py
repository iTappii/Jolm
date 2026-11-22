from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    database_url: str = "postgresql://jol:jol_dev_password@localhost:5433/jol"
    test_database_url: str = "postgresql://jol:jol_dev_password@localhost:5433/jol_test"
    db_pool_min: int = 1
    db_pool_max: int = 10
    min_ios_version: str = "1.0.0"

    worker_batch_size: int = 5
    worker_poll_interval_sec: float = 2.0
    worker_max_attempts: int = 5
    worker_lease_sec: int = 300  # a claimed job not finished within this is taken by another worker

    apple_client_id: str = "kz.jol.app"
    # Sign in with Apple server credentials, needed to exchange the authorization code and to
    # revoke the grant on account deletion. CREDENTIAL GAP: not provisioned yet (Apple Developer
    # team ID, a Sign in with Apple key ID and its .p8 private key); empty means "not configured".
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: SecretStr = SecretStr("")
    # Push (Ш-40). "log" sends nothing (dev, tests); "apns" needs the key below.
    # CREDENTIAL GAP: no paid Apple Developer account yet, so no team id / push key id / .p8 key.
    push_provider: str = "log"
    apns_team_id: str = ""
    apns_key_id: str = ""
    apns_private_key: SecretStr = SecretStr("")  # contents of the .p8 file ("\n" escapes allowed)
    apns_topic: str = ""  # the app's bundle id; empty = apple_client_id
    apns_sandbox: bool = True  # development builds use the sandbox host
    # Secrets (Ш-51). `auth_secret` is the legacy single key: in dev/test it is the fallback for the
    # four below; in any other APP_ENV each of the four must be set (distinct, >= 32 bytes) or the
    # API and the worker refuse to start (app/auth/keys.py). See docs/deploy.md.
    auth_secret: SecretStr = SecretStr("")
    jwt_secret: SecretStr = SecretStr("")  # signs access tokens
    otp_secret: SecretStr = SecretStr("")  # HMAC of one-time codes, destinations and IPs
    apple_challenge_secret: SecretStr = SecretStr("")  # signs the Sign in with Apple nonce
    # Fernet keys (urlsafe base64, 32 bytes) for tokens stored at rest, comma separated: the first
    # encrypts, all of them decrypt (rotation). Generate: `python -m app.auth.keys generate`.
    token_encryption_keys: SecretStr = SecretStr("")
    # Old AUTH_SECRET, only while Apple tokens encrypted before Ш-51 still exist (decrypt-only).
    legacy_token_secret: SecretStr = SecretStr("")
    # Reverse proxies whose X-Forwarded-For is believed (IPs/CIDRs, comma separated;
    # app/clientip.py).
    trusted_proxies: str = ""
    # Observability (Ш-51): both off by default.
    sentry_dsn: str = ""  # Sentry-compatible DSN; needs `pip install sentry-sdk` (optional extra)
    sentry_traces_sample_rate: float = 0.0
    metrics_token: SecretStr = SecretStr(
        ""
    )  # bearer token for GET /metrics; empty = off outside dev

    admin_login_max_failures: int = 5
    admin_login_window_min: int = 15

    llm_provider: str = "fake"
    # DeepSeek (Ш-53): the key only from the environment, never committed
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_timeout_sec: float = 60.0
    llm_max_retries: int = 2
    # Chat limits (Ш-30/31). Counted in PostgreSQL (`rate_limit_hits`, Ш-51), shared by all API
    # processes; only hashed keys and timestamps are stored, never chat content.
    guest_chat_install_limit: int = 20  # requests per window per X-Install-ID
    guest_chat_ip_limit: int = 60  # requests per window per client IP (NAT-friendly)
    guest_chat_window_sec: int = 3600
    chat_user_limit: int = 60  # messages per window per registered user
    chat_user_window_sec: int = 3600
    # Analytics batches (Ш-50), counted like the chat's: per X-Install-ID and per IP
    analytics_install_limit: int = 120
    analytics_ip_limit: int = 600
    analytics_window_sec: int = 3600
    sms_provider: str = ""
    email_provider: str = "stub"
    valhalla_url: Optional[str] = None
    open_meteo_url: str = "https://api.open-meteo.com"
    # Commercial use of Open-Meteo needs the paid plan (Ш-39); empty = the free, non-commercial API.
    open_meteo_api_key: SecretStr = SecretStr("")
    # Base URL of the photo storage (Ш-44): photo previews in the offline trip (Ш-42) are
    # `<media_base_url>/<storage_key>`; empty = no photo URLs yet (they are null).
    media_base_url: str = ""
    # Object storage for user uploads (Ш-44): "" = none (uploads answer 503), "s3" = any
    # S3-compatible service (MinIO in dev), "local" = files on disk, dev/test only.
    storage_provider: str = ""
    s3_endpoint: str = ""  # e.g. http://127.0.0.1:9000 (path-style addressing)
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: SecretStr = SecretStr("")
    storage_local_dir: str = ""  # empty = <system temp>/jol-media-dev
    storage_local_upload_base: str = "http://127.0.0.1:8000"  # where the dev PUT endpoint is


@lru_cache
def get_settings() -> Settings:
    return Settings()
