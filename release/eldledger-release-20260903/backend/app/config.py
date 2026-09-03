from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> str:
    docker_data = Path("/data")
    if docker_data.is_dir():
        return str(docker_data)
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / "data")


def sqlite_url_for(db_path: Path) -> str:
    return "sqlite:///" + db_path.resolve().as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "eldLedger"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    database_url: str = ""
    backend_cors_origins: str = (
        "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173"
    )
    data_dir: str = Field(default_factory=_default_data_dir)

    @model_validator(mode="after")
    def apply_database_url(self) -> Self:
        if not self.database_url:
            db_path = Path(self.data_dir) / "database" / "eldledger.db"
            self.database_url = sqlite_url_for(db_path)
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


settings = Settings()
