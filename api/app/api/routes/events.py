from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.event import EventResponse
from ...services.audit_service import list_events as list_audit_events


router = APIRouter()


@router.get(
    "/api/v1/events",
    response_model=list[EventResponse],
    tags=["Events"],
    operation_id="list_events",
)
async def list_events_route(
    customer_id: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None, alias="type"),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[EventResponse]:
    events = list_audit_events(
        db,
        lab_group=None if x_lab_group == "anonymous" else x_lab_group,
        customer_id=customer_id,
        order_id=order_id,
        event_type=event_type,
        source=source,
        limit=limit,
    )
    return [EventResponse.model_validate(event) for event in events]
