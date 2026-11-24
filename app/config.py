import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        secret = os.getenv("STORESTOCK_SECRET")
        if not secret:
            raise RuntimeError("STORESTOCK_SECRET environment variable is missing")
        self.secret_key: str = secret
        base_dir = Path(__file__).resolve().parent.parent
        self.db_path: str = os.getenv("STORESTOCK_DB_PATH", str(base_dir / "storestock.db"))
        self.algorithm: str = "HS256"
        self.token_expire_seconds: int = 8 * 3600


def get_settings() -> Settings:
    return Settings()
