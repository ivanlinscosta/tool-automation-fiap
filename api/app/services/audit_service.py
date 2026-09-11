import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event


def create_event(
    db: Session,
    event_type: str,
    student_id: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any] | None = None,
) -> Event:
    event = Event(
        event_id=f"EV-{uuid4().hex[:12].upper()}",
        event_type=event_type,
        student_id=student_id,
        timestamp=datetime.utcnow(),
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(db: Session, student_id: str | None = None) -> list[Event]:
    query = select(Event)
    if student_id:
        query = query.where(Event.student_id == student_id)
    query = query.order_by(Event.timestamp.desc())
    return list(db.execute(query).scalars().all())
