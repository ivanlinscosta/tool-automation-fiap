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

    # --- Workflow Labs (FIAP) -------------------------------------------------
    # Fixed seed shared by every lab data generator so all payloads are reproducible.
    LABS_SEED: int = 2026
    # Reference "today" used to build temporally coherent lab datasets.
    LABS_TODAY: str = "2026-09-13"
    # Minimum operational records seeded per lab group.
    LABS_MIN_RECORDS: int = 1000
    # Enables the controlled ?scenario= failure simulation. Lab routes only.
    LABS_ALLOW_SCENARIOS: bool = True
    # Seconds a lab endpoint waits when scenario=timeout is requested.
    LABS_SCENARIO_TIMEOUT_SECONDS: int = 5
    # Seed every lab group during application startup instead of lazily on first access.
    LABS_SEED_ON_STARTUP: bool = False
    # When set, instructor endpoints under /api/v1/labs require a matching X-Instructor-Key header.
    LABS_INSTRUCTOR_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()