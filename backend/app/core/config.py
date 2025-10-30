from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment."""

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AUDEX"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    STORAGE_PATH: str = "tmp/uploads"
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./audex.db",
        description="SQLAlchemy database URL",
    )
    OCR_ENGINE: str = Field(default="easyocr", description="OCR engine identifier")
    OCR_LANGUAGES: list[str] = Field(default_factory=lambda: ["fr", "en"])
    VISION_MODEL_PATH: str = Field(default="ultralytics/yolov8n.pt")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
