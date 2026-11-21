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
    auth_secret: SecretStr = SecretStr("")

    admin_login_max_failures: int = 5
    admin_login_window_min: int = 15

    llm_provider: str = "fake"
    llm_timeout_sec: float = 60.0
    llm_max_retries: int = 2
    # Chat limits (Ш-30/31). Guest counters live in process memory (nothing is written for guests).
    guest_chat_install_limit: int = 20  # requests per window per X-Install-ID
    guest_chat_ip_limit: int = 60  # requests per window per client IP (NAT-friendly)
    guest_chat_window_sec: int = 3600
    chat_user_limit: int = 60  # messages per window per registered user
    chat_user_window_sec: int = 3600
    sms_provider: str = ""
    email_provider: str = "stub"
    valhalla_url: Optional[str] = None
    open_meteo_url: str = "https://api.open-meteo.com"
    # Commercial use of Open-Meteo needs the paid plan (Ш-39); empty = the free, non-commercial API.
    open_meteo_api_key: SecretStr = SecretStr("")
    # Base URL of the photo storage (Ш-44): photo previews in the offline trip (Ш-42) are
    # `<media_base_url>/<storage_key>`; empty = no photo URLs yet (they are null).
    media_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
