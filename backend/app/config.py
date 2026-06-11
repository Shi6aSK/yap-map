try:
    # pydantic v1
    from pydantic import BaseSettings
except Exception:
    # pydantic v2 moved BaseSettings to pydantic-settings
    from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "YapMap"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./yapmap.db"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    TRANSCRIPTION_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    AUDIO_CHUNK_MS: int = 500
    MAX_UPLOAD_MB: int = 500

    class Config:
        env_file = ".env"


settings = Settings()
