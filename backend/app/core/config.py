from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment."""

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AUDEX"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    STORAGE_PATH: str = "tmp/uploads"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
