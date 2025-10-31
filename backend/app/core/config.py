from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


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
    LOG_LEVEL: str = Field(default="INFO", description="Root logging level")
    LOG_FORMAT: str | None = Field(
        default=None,
        description="Custom logging formatter pattern (optional).",
    )
    LOG_DATE_FORMAT: str | None = Field(
        default=None,
        description="Custom logging date format (optional).",
    )
    LOG_FILE: str | None = Field(
        default="audex.log",
        description="Optional path to a file where logs should be written.",
    )
    OCR_ENGINE: str = Field(default="easyocr", description="OCR engine identifier")
    OCR_LANGUAGES: list[str] = Field(default_factory=lambda: ["fr", "en"])
    VISION_MODEL_PATH: str = Field(default="ultralytics/yolov8n.pt")
    VISION_ENABLE_YOLO: bool = Field(default=True, description="Enable YOLO vision engine (fallback to legacy if false)")
    GEMINI_ENABLED: bool = Field(default=False, description="Enable Gemini advanced analysis")
    GEMINI_REQUIRED: bool = Field(default=False, description="Treat Gemini failures as blocking")
    GEMINI_API_KEY: str | None = Field(default=None)
    GEMINI_MODEL: str = Field(default="gemini-2.0-flash-exp")
    GEMINI_TIMEOUT_SECONDS: int = Field(default=15, description="Timeout per Gemini request (seconds)")
    GEMINI_MAX_RETRIES: int = Field(default=2, description="Maximum retries for Gemini calls")
    EASY_OCR_DOWNLOAD_ENABLED: bool = Field(
        default=True,
        description="Allow EasyOCR to download missing model weights at runtime",
    )
    GEMINI_SUMMARY_ENABLED: bool = Field(default=False, description="Enable Gemini summary generation")
    GEMINI_SUMMARY_REQUIRED: bool = Field(default=False, description="Treat summary failures as blocking")
    GEMINI_SUMMARY_API_KEY: str | None = Field(default=None)
    GEMINI_SUMMARY_MODEL: str = Field(default="gemini-2.0-flash-exp")
    GEMINI_SUMMARY_TIMEOUT_SECONDS: int = Field(default=30, description="Timeout per summary request (seconds)")
    GEMINI_SUMMARY_MAX_RETRIES: int = Field(default=2, description="Maximum retries for summary generation")
    SUMMARY_FALLBACK_ENABLED: bool = Field(
        default=False,
        description="Enable local fallback model when Gemini summary is unavailable",
    )
    SUMMARY_FALLBACK_MODEL: str = Field(default="ollama/llama3.1", description="Fallback model identifier")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("OCR_LANGUAGES", mode="before")
    @classmethod
    def _coerce_languages(cls, value):  # noqa: D401 - simple normalizer
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",")]
            return [item for item in items if item]
        return value


settings = Settings()
