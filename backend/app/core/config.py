from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Onboard Chaser AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/onboard_chaser"

    # JWT / Authentication
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    MAGIC_TOKEN_EXPIRE_HOURS: int = 72

    # Cloudflare R2 Storage
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "onboard-chaser-documents"
    R2_ENDPOINT_URL: str = ""

    # Resend Email
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "onboarding@onboardchaser.ai"

    # Celery / Redis
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # US08/US09 — Automated reminder configuration.
    # These REMINDER_* env vars are the configuration surface US09 will build
    # its admin UI on top of; US08 reads them live at evaluation time with the
    # defaults below as safe fallbacks. See app/services/reminder_service.py
    # for how each knob is applied.
    REMINDER_ENABLED: bool = True              # master switch for the reminder system
    REMINDER_SCAN_INTERVAL_MINUTES: int = 60   # celery-beat scan interval (hourly)
    REMINDER_MIDWAY_PERCENT: float = 0.5       # remind once 50% of token lifetime elapsed
    REMINDER_EXPIRY_WINDOW_HOURS: int = 24     # remind again within 24h of link expiry
    REMINDER_COOLDOWN_HOURS: int = 24          # min interval between two send attempts
    REMINDER_MAX_COUNT: int = 3                # max successfully-sent reminders per onboarding

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
