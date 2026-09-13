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
    title="Quantum Commerce API",
    description=(
        "API oficial do case fictício Quantum Commerce — disciplina Tools, Automations and Workflows (FIAP). "
        "Backend determinístico para agentes n8n, Dify, Power Automate e Python. Sem LLM no backend."
    ),
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
from .api.routes.catalog import router as catalog_router
from .api.routes.customers import router as customers_router
from .api.routes.events import router as events_router
from .api.routes.health import router as health_router
from .api.routes.interactions import router as interactions_router
from .api.routes.inventory import router as inventory_router
from .api.routes.lab import router as lab_router
from .api.routes.logistics import router as logistics_router
from .api.routes.meta import router as meta_router
from .api.routes.orders import router as orders_router
from .api.routes.policies import router as policies_router
from .api.routes.promotions import router as promotions_router
from .api.routes.refunds import router as refunds_router
from .api.routes.returns import router as returns_router
from .api.routes.root import router as root_router
from .api.routes.support import router as support_router

app.include_router(root_router)
app.include_router(health_router)
app.include_router(customers_router)
app.include_router(catalog_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(logistics_router)
app.include_router(policies_router)
app.include_router(returns_router)
app.include_router(support_router)
app.include_router(approvals_router)
app.include_router(refunds_router)
app.include_router(promotions_router)
app.include_router(interactions_router)
app.include_router(events_router)
app.include_router(meta_router)
app.include_router(lab_router)