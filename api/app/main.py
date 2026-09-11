import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db.database import init_db
from .db.seed import seed_data
from .middleware.request_context import RequestContextMiddleware


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
    title="FIAP Student Desk Lab API",
    description="Central Inteligente de Solicitações Acadêmicas — pedagogical API for automation lab",
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

from .api.routes.approvals import router as approvals_router
from .api.routes.departments import router as departments_router
from .api.routes.events import router as events_router
from .api.routes.health import router as health_router
from .api.routes.interactions import router as interactions_router
from .api.routes.knowledge import router as knowledge_router
from .api.routes.lab import router as lab_router
from .api.routes.priority import router as priority_router
from .api.routes.requests import router as requests_router
from .api.routes.root import router as root_router
from .api.routes.students import router as students_router

app.include_router(root_router)
app.include_router(health_router)
app.include_router(students_router)
app.include_router(departments_router)
app.include_router(knowledge_router)
app.include_router(priority_router)
app.include_router(requests_router)
app.include_router(interactions_router)
app.include_router(approvals_router)
app.include_router(events_router)
app.include_router(lab_router)
