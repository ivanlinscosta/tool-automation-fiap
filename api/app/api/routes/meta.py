from typing import Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db.database import get_db
from ...models.approval import Approval
from ...models.customer import Customer
from ...models.event import Event
from ...models.interaction import Interaction
from ...models.order import Order
from ...models.policy import Policy
from ...models.product import Product
from ...models.promotion import Promotion
from ...models.refund import Refund
from ...models.return_record import ReturnRecord
from ...models.shipment import Shipment
from ...models.support_case import SupportCase


router = APIRouter()

LAB_ENDPOINTS = [
    "/api/v1/lab/slow",
    "/api/v1/lab/error",
    "/api/v1/lab/rate-limit",
    "/api/v1/lab/not-found",
    "/api/v1/lab/validation",
]


def _count_rows(db: Session, model: type[Any]) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


@router.get(
    "/api/v1/meta",
    response_model=dict,
    tags=["Meta"],
    operation_id="get_meta",
)
async def get_meta(
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = x_lab_group
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "api_base": "/api/v1",
        "docs": "/docs",
        "health": "/api/v1/health",
        "openapi": "/openapi.json",
        "environment": settings.ENVIRONMENT,
        "seed_today": "2026-09-13",
        "seeded_entities": {
            "customers": _count_rows(db, Customer),
            "products": _count_rows(db, Product),
            "orders": _count_rows(db, Order),
            "shipments": _count_rows(db, Shipment),
            "policies": _count_rows(db, Policy),
            "support_cases": _count_rows(db, SupportCase),
            "return_records": _count_rows(db, ReturnRecord),
            "approvals": _count_rows(db, Approval),
            "refunds": _count_rows(db, Refund),
            "promotions": _count_rows(db, Promotion),
            "interactions": _count_rows(db, Interaction),
            "events": _count_rows(db, Event),
        },
        "lab_endpoints": LAB_ENDPOINTS,
        "links": {},
    }
