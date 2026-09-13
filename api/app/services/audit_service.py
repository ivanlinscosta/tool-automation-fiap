import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.event import Event


EVENT_TYPES = {
    "order_lookup",
    "inventory_lookup",
    "customer_lookup",
    "product_lookup",
    "return_created",
    "return_eligibility_checked",
    "support_case_created",
    "refund_requested",
    "refund_created",
    "approval_requested",
    "approval_decision",
    "interaction_created",
    "policy_searched",
    "priority_checked",
    "promotion_checked",
    "shipment_lookup",
    "lab_error_triggered",
}


def create_event(
    db: Session,
    event_type: str,
    lab_group: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any] | None = None,
    customer_id: str | None = None,
) -> Event:
    event = Event(
        event_id=f"EV-{uuid4().hex[:12].upper()}",
        event_type=event_type,
        lab_group=lab_group,
        customer_id=customer_id,
        timestamp=datetime.now(UTC),
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(
    db: Session,
    lab_group: str | None = None,
    customer_id: str | None = None,
    order_id: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[Event]:
    query = select(Event)
    if lab_group:
        query = query.where(Event.lab_group == lab_group)
    if customer_id:
        query = query.where(Event.customer_id == customer_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if source:
        query = query.where(Event.metadata_json.like(f'%"source": "{source}"%'))
    if order_id:
        query = query.where(Event.metadata_json.like(f'%"order_id": "{order_id}"%'))
    query = query.order_by(Event.timestamp.desc()).limit(limit)
    return list(db.execute(query).scalars().all())