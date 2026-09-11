import logging
from importlib import import_module
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import settings


logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    for module_name in (
        "app.models.access_request",
        "app.models.employee",
        "app.models.event",
        "app.models.team",
        "app.models.ticket",
    ):
        import_module(module_name)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")
