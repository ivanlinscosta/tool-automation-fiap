from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Quantum Commerce API"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./quantum_commerce.db"
    CORS_ORIGINS: str = "*"
    LOG_LEVEL: str = "INFO"
    VERSION: str = "2.0.0"

    # Refunds above this amount require a valid, approved approval_id.
    REFUND_APPROVAL_THRESHOLD: float = 500.0

    # Default return window (days) for the deterministic eligibility rule.
    RETURN_WINDOW_DAYS: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()