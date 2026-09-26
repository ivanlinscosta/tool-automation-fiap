import logging
from importlib import import_module
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ..config import settings


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


BASE_MODELS = (
    "app.models.approval",
    "app.models.customer",
    "app.models.event",
    "app.models.idempotency",
    "app.models.interaction",
    "app.models.inventory",
    "app.models.order",
    "app.models.policy",
    "app.models.product",
    "app.models.promotion",
    "app.models.refund",
    "app.models.return_record",
    "app.models.shipment",
    "app.models.support_case",
)

LAB_MODELS_PACKAGE = "app.models.labs"


def _lab_model_modules() -> list[str]:
    package_dir = Path(__file__).resolve().parent.parent / "models" / "labs"
    if not package_dir.is_dir():
        return []
    return sorted(
        f"{LAB_MODELS_PACKAGE}.{path.stem}"
        for path in package_dir.glob("group*.py")
        if not path.stem.startswith("__")
    )


def init_db() -> None:
    for module_name in (*BASE_MODELS, *_lab_model_modules()):
        import_module(module_name)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")