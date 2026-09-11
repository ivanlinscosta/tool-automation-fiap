import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.event import Event


EVENT_TYPES = {
    "student_queried",
    "knowledge_searched",
    "automatic_answer_generated",
    "request_created",
    "request_updated",
    "priority_checked",
    "department_queried",
    "approval_requested",
    "approval_approved",
    "approval_rejected",
    "lab_error_triggered",
}


def create_event(
    db: Session,
    event_type: str,
    student_id: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any] | None = None,
    fictional_student_id: str | None = None,
) -> Event:
    event = Event(
        event_id=f"EV-{uuid4().hex[:12].upper()}",
        event_type=event_type,
        student_id=student_id,
        fictional_student_id=fictional_student_id,
        timestamp=datetime.now(UTC),
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(db: Session, student_id: str | None = None, event_type: str | None = None) -> list[Event]:
    query = select(Event)
    if student_id:
        query = query.where(Event.student_id == student_id)
    if event_type:
        query = query.where(Event.event_type == event_type)
    query = query.order_by(Event.timestamp.desc())
    return list(db.execute(query).scalars().all())
