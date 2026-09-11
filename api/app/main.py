import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import init_db
from app.db.seed import seed_data
from app.middleware.request_context import RequestContextMiddleware


logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def _get_cors_origins() -> list[str]:
    if settings.CORS_ORIGINS.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_data()
    yield


app = FastAPI(
    title="FlowDesk Lab API",
    description="Pedagogical API for automation lab - Tools, Automations and Workflows",
    version=settings.VERSION,
    lifespan=lifespan,
)

cors_origins = _get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

from app.api.routes.health import router as health_router
from app.api.routes.root import router as root_router
from app.api.routes.employees import router as employees_router
from app.api.routes.teams import router as teams_router
from app.api.routes.priority import router as priority_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.access_requests import router as access_requests_router
from app.api.routes.events import router as events_router
from app.api.routes.lab import router as lab_router

app.include_router(root_router)
app.include_router(health_router)
app.include_router(employees_router)
app.include_router(teams_router)
app.include_router(priority_router)
app.include_router(tickets_router)
app.include_router(access_requests_router)
app.include_router(events_router)
app.include_router(lab_router)
