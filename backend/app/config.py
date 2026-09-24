"""Settings loaded from environment variables / an .env file.

The .env location defaults to the repo root and can be moved anywhere by
setting ENV_FILE to its path. Values are never returned by the API; only
whether each one is set.
"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DATA_DIR = BACKEND_DIR / "data"


def env_file_path() -> Path:
    return Path(os.environ.get("ENV_FILE") or REPO_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    auspost_base_url: str = ""
    auspost_api_key: str = ""
    auspost_password: str = ""
    auspost_account: str = ""
    startrack_account: str = ""
    auspost_product_id: str = ""
    startrack_product_id: str = ""

    tnt_weblink_username: str = ""
    tnt_weblink_password: str = ""
    tnt_uat_username: str = ""
    tnt_uat_password: str = ""
    tnt_account: str = ""

    courier_timeout_seconds: float = 10.0
    data_dir: Path = DEFAULT_DATA_DIR


# Names reported by /api/health (true/false only).
REPORTED_FIELDS = [
    "auspost_base_url", "auspost_api_key", "auspost_password",
    "auspost_account", "startrack_account",
    "auspost_product_id", "startrack_product_id",
    "tnt_weblink_username", "tnt_weblink_password",
    "tnt_uat_username", "tnt_uat_password", "tnt_account",
]


def get_settings() -> Settings:
    return Settings(_env_file=env_file_path(), _env_file_encoding="utf-8")
