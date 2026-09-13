#!/usr/bin/env python3

from __future__ import annotations

import os
import sys

from sqlalchemy import func, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_data
from app.models.approval import Approval
from app.models.customer import Customer
from app.models.event import Event
from app.models.interaction import Interaction
from app.models.order import Order
from app.models.policy import Policy
from app.models.product import Product
from app.models.promotion import Promotion
from app.models.refund import Refund
from app.models.return_record import ReturnRecord
from app.models.shipment import Shipment
from app.models.support_case import SupportCase


def _count_rows(session, model) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def main() -> int:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_data()

    session = SessionLocal()
    try:
        print("Quantum Commerce lab database reset and seeded.")
        print(
            {
                "customers": _count_rows(session, Customer),
                "products": _count_rows(session, Product),
                "orders": _count_rows(session, Order),
                "shipments": _count_rows(session, Shipment),
                "policies": _count_rows(session, Policy),
                "support_cases": _count_rows(session, SupportCase),
                "return_records": _count_rows(session, ReturnRecord),
                "approvals": _count_rows(session, Approval),
                "refunds": _count_rows(session, Refund),
                "promotions": _count_rows(session, Promotion),
                "interactions": _count_rows(session, Interaction),
                "events": _count_rows(session, Event),
            }
        )
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
