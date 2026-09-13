from __future__ import annotations

import importlib
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

database_module = cast(Any, importlib.import_module("app.db.database"))
seed_module = cast(Any, importlib.import_module("app.db.seed"))
main_module = cast(Any, importlib.import_module("app.main"))

Base = database_module.Base
get_db = database_module.get_db
app = main_module.app


@pytest.fixture(autouse=True)
def setup_database(tmp_path: Path) -> Generator[None, None, None]:
    test_database_path = tmp_path / "test_quantum_commerce.db"
    test_database_url = f"sqlite:///{test_database_path}"

    engine = create_engine(test_database_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    database_module.engine = engine
    database_module.SessionLocal = testing_session_local
    seed_module.SessionLocal = testing_session_local

    Base.metadata.create_all(bind=engine)
    seed_module.seed_data()

    lab_module = importlib.import_module("app.api.routes.lab")
    lab_module._rate_limit_tracker.clear()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    db = database_module.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def make_headers() -> Callable[[str, str], dict[str, str]]:
    def _make_headers(lab_group: str = "grupo-01", request_id: str = "req-001") -> dict[str, str]:
        return {"X-Lab-Group": lab_group, "X-Request-ID": request_id}

    return _make_headers
