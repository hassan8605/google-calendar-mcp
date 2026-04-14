from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # ─── Application ───────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 4325
    ENVIRONMENT: str = "development"

    # ─── Anthropic ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # ─── Google Calendar ───────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:4325/api/calendar/auth/callback"
    GOOGLE_TOKENS_DIR: str = "/app/tokens"   # one JSON file per user inside this dir
    GOOGLE_DEFAULT_CALENDAR: str = "primary"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
