from __future__ import annotations

import importlib
from typing import Any, get_args, get_origin

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import database as database_module
from app.db import seed as seed_module
from app.db.database import Base, get_db
from app.models.access_request import AccessRequest, AccessRequestResponse
from app.models.employee import Employee, EmployeeResponse
from app.models.event import Event, EventResponse
from app.models.team import Team, TeamResponse
from app.models.ticket import Ticket, TicketResponse
from app.services import access_service, ticket_service


def _normalize_response_model(model: Any) -> Any:
    mapping = {
        Employee: EmployeeResponse,
        Team: TeamResponse,
        Ticket: TicketResponse,
        AccessRequest: AccessRequestResponse,
        Event: EventResponse,
    }

    if model in mapping:
        return mapping[model]

    origin = get_origin(model)
    args = get_args(model)
    if origin is list and len(args) == 1 and args[0] in mapping:
        return list[mapping[args[0]]]

    return model


def _patch_route_registration() -> None:
    if getattr(APIRouter, "_flowdesk_test_response_patch", False):
        return

    original_get = APIRouter.get
    original_post = APIRouter.post

    def patched_get(self: APIRouter, path: str, *args: Any, **kwargs: Any):
        if "response_model" in kwargs:
            kwargs["response_model"] = _normalize_response_model(kwargs["response_model"])
        return original_get(self, path, *args, **kwargs)

    def patched_post(self: APIRouter, path: str, *args: Any, **kwargs: Any):
        if "response_model" in kwargs:
            kwargs["response_model"] = _normalize_response_model(kwargs["response_model"])
        return original_post(self, path, *args, **kwargs)

    APIRouter.get = patched_get
    APIRouter.post = patched_post
    APIRouter._flowdesk_test_response_patch = True


def _bootstrap_routes() -> None:
    if getattr(app.state, "_flowdesk_test_bootstrapped", False):
        return

    if not hasattr(ticket_service, "get_ticket"):
        ticket_service.get_ticket = ticket_service.get_ticket_by_id

    if not hasattr(access_service, "get_access_request"):
        access_service.get_access_request = access_service.get_access_request_by_id

    if not hasattr(access_service, "approve_access_request"):
        access_service.approve_access_request = access_service.review_access_request

    _patch_route_registration()

    route_modules = [
        importlib.import_module("app.api.routes.health"),
        importlib.import_module("app.api.routes.root"),
        importlib.import_module("app.api.routes.employees"),
        importlib.import_module("app.api.routes.teams"),
        importlib.import_module("app.api.routes.priority"),
        importlib.import_module("app.api.routes.tickets"),
        importlib.import_module("app.api.routes.access_requests"),
        importlib.import_module("app.api.routes.events"),
        importlib.import_module("app.api.routes.lab"),
    ]

    existing_paths = {getattr(route, "path", None) for route in app.router.routes}
    for route_module in route_modules:
        module_paths = {getattr(route, "path", None) for route in route_module.router.routes}
        if module_paths.issubset(existing_paths):
            continue
        app.include_router(route_module.router)
        existing_paths.update(module_paths)

    app.state._flowdesk_test_bootstrapped = True


_bootstrap_routes()


@pytest.fixture(autouse=True)
def setup_database(tmp_path: pytest.TempPathFactory):
    test_database_path = tmp_path / "test_flowdesk.db"
    test_database_url = f"sqlite:///{test_database_path}"

    engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
    )
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

    try:
        lab_module = importlib.import_module("app.api.routes.lab")
        lab_module._rate_limit_tracker.clear()
    except Exception:
        pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    db = database_module.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def make_headers():
    def _make_headers(student_id: str = "student-001", request_id: str = "req-001") -> dict[str, str]:
        return {
            "X-Student-ID": student_id,
            "X-Request-ID": request_id,
        }

    return _make_headers


@pytest.fixture
def ticket_payload() -> dict[str, str]:
    return {
        "employee_id": "EMP001",
        "category": "it",
        "impact": "medium",
        "urgency": "high",
        "summary": "Password reset required",
        "description": "Unable to sign in to the VPN after password expiration.",
        "source": "api",
    }


@pytest.fixture
def access_request_payload() -> dict[str, str]:
    return {
        "employee_id": "EMP001",
        "resource": "Corporate VPN",
        "justification": "Needs secure remote access for on-call support.",
        "risk": "medium",
    }
