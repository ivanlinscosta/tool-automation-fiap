from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.event import EventResponse
from ...services.audit_service import EVENT_TYPES, list_events


router = APIRouter()


@router.get(
    "/api/v1/events",
    response_model=list[EventResponse],
    tags=["Events"],
    operation_id="list_events",
    summary="List audit events",
    description=(
        "List audit events filtered by the X-Student-ID lab group header. "
        f"Supported event types: {', '.join(sorted(EVENT_TYPES))}."
    ),
    responses={200: {"description": "Events retrieved successfully"}},
)
async def list_events_route(
    event_type: str | None = Query(default=None),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> list[EventResponse]:
    _ = x_request_id
    return [EventResponse.model_validate(event) for event in list_events(db=db, student_id=x_student_id, event_type=event_type)]
