from functools import lru_cache
from pathlib import Path
from typing import Optional

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

    admin_login_max_failures: int = 5
    admin_login_window_min: int = 15

    llm_provider: str = "stub"
    sms_provider: str = "stub"
    email_provider: str = "stub"
    valhalla_url: Optional[str] = None
    open_meteo_url: str = "https://api.open-meteo.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
