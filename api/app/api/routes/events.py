from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.event import Event, EventResponse
from app.services.audit_service import list_events


router = APIRouter()


async def _call_list_events(function: Any, fallback_args: list[tuple[Any, ...]], **kwargs: Any) -> Any:
    try:
        signature = inspect.signature(function)
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        supported_kwargs = (
            kwargs
            if accepts_kwargs
            else {key: value for key, value in kwargs.items() if key in signature.parameters}
        )
        if supported_kwargs:
            result = function(**supported_kwargs)
        else:
            raise TypeError("No matching keyword arguments")
    except TypeError:
        last_error: TypeError | None = None
        for args in fallback_args:
            try:
                result = function(*args)
                break
            except TypeError as exc:
                last_error = exc
        else:
            if last_error is not None:
                raise last_error
            raise

    if inspect.isawaitable(result):
        return await result
    return result


def _value_from_event(item: Any, candidate_keys: tuple[str, ...]) -> Any:
    for key in candidate_keys:
        if isinstance(item, dict) and key in item:
            return item[key]
        if hasattr(item, key):
            return getattr(item, key)
    return None


def _matches_filter(item: Any, candidate_keys: tuple[str, ...], expected: str | None) -> bool:
    if expected is None:
        return True
    actual = _value_from_event(item, candidate_keys)
    if actual is None:
        return True
    return str(actual).lower() == expected.lower()


@router.get(
    "/api/v1/events",
    response_model=list[EventResponse],
    tags=["Events"],
    operation_id="list_events",
    summary="List audit events",
    description="List audit events, automatically filtered by the X-Student-ID header with an optional event type filter.",
    responses={200: {"description": "Events retrieved successfully"}},
)
async def list_events_route(
    event_type: str | None = Query(default=None),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> list[EventResponse]:
    events = await _call_list_events(
        list_events,
        fallback_args=[
            (db, x_student_id, event_type, x_request_id),
            (db, x_student_id, event_type),
            (x_student_id, event_type, db),
            (db, x_student_id),
            (x_student_id, db),
            (db,),
        ],
        db=db,
        student_id=x_student_id,
        event_type=event_type,
        request_id=x_request_id,
    )
    event_list = list(events or [])
    return [
        event
        for event in event_list
        if _matches_filter(event, ("student_id", "requester_student_id", "created_by_student_id"), x_student_id)
        and _matches_filter(event, ("event_type", "type"), event_type)
    ]
