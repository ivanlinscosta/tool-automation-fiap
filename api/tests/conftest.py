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
    test_database_path = tmp_path / "test_fiap_student_desk.db"
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
    def _make_headers(student_id: str = "grupo-01", request_id: str = "req-001") -> dict[str, str]:
        return {"X-Student-ID": student_id, "X-Request-ID": request_id}

    return _make_headers


@pytest.fixture
def request_payload() -> dict[str, str]:
    return {
        "student_id": "STU001",
        "category": "academic_services",
        "priority": "medium",
        "summary": "Need enrollment declaration",
        "description": "Fictional didactic request for an enrollment declaration.",
        "source": "api",
    }


@pytest.fixture
def approval_request_payload() -> dict[str, str]:
    return {
        "student_id": "STU001",
        "request_type": "visitor_campus_authorization",
        "justification": "Fictional didactic approval flow for campus access.",
        "risk": "medium",
    }


@pytest.fixture
def interaction_payload() -> dict[str, object]:
    return {
        "student_id": "STU001",
        "request_text": "Como acesso o ambiente virtual?",
        "category": "digital_learning",
        "response_type": "automatic",
        "response_text": "Use a orientação didática do artigo KB001.",
        "knowledge_articles": ["KB001"],
        "source": "api",
    }
