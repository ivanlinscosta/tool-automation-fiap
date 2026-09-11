from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "FIAP Student Desk Lab API"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./fiap_student_desk.db"
    CORS_ORIGINS: str = "*"
    LOG_LEVEL: str = "INFO"
    VERSION: str = "1.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
