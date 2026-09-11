from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.ticket import Ticket, TicketCreate, TicketFilter, TicketResponse
from app.services.ticket_service import create_ticket, get_ticket, list_tickets


router = APIRouter()


async def _call_service(function: Any, fallback_args: list[tuple[Any, ...]], **kwargs: Any) -> Any:
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


def _build_ticket_filter(
    employee_id: str | None,
    category: str | None,
    priority: str | None,
    ticket_status: str | None,
    student_id: str,
) -> TicketFilter:
    model_fields = getattr(TicketFilter, "model_fields", None) or getattr(TicketFilter, "__fields__", {})
    payload = {
        "employee_id": employee_id,
        "category": category,
        "priority": priority,
        "status": ticket_status,
        "student_id": student_id,
    }
    filtered_payload = {
        key: value
        for key, value in payload.items()
        if value is not None and (not model_fields or key in model_fields)
    }
    if hasattr(TicketFilter, "model_validate"):
        return TicketFilter.model_validate(filtered_payload)
    return TicketFilter(**filtered_payload)


def _value_from_item(item: Any, candidate_keys: tuple[str, ...]) -> Any:
    for key in candidate_keys:
        if isinstance(item, dict) and key in item:
            return item[key]
        if hasattr(item, key):
            return getattr(item, key)
    return None


def _matches_filter(item: Any, candidate_keys: tuple[str, ...], expected: str | None) -> bool:
    if expected is None:
        return True
    actual = _value_from_item(item, candidate_keys)
    if actual is None:
        return True
    return str(actual).lower() == expected.lower()


@router.post(
    "/api/v1/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tickets"],
    operation_id="create_ticket",
    summary="Create ticket",
    description="Create a new ticket and automatically assign the responsible team.",
    responses={
        201: {"description": "Ticket created successfully"},
        422: {"description": "Validation error"},
    },
)
async def create_ticket_route(
    ticket_data: TicketCreate = Body(
        ...,
        openapi_examples={
            "wifi_issue": {
                "summary": "WiFi connectivity issue",
                "value": {
                    "employee_id": "EMP001",
                    "category": "it",
                    "impact": "high",
                    "urgency": "high",
                    "summary": "Notebook cannot connect to WiFi",
                    "description": "Notebook has not been able to connect to WiFi since yesterday.",
                    "source": "n8n",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> TicketResponse:
    created_ticket = await _call_service(
        create_ticket,
        fallback_args=[
            (ticket_data, db, x_student_id, x_request_id),
            (db, ticket_data, x_student_id, x_request_id),
            (ticket_data, db),
            (db, ticket_data),
            (ticket_data,),
        ],
        db=db,
        ticket=ticket_data,
        ticket_data=ticket_data,
        payload=ticket_data,
        student_id=x_student_id,
        request_id=x_request_id,
    )
    return created_ticket


@router.get(
    "/api/v1/tickets/{ticket_id}",
    response_model=TicketResponse,
    tags=["Tickets"],
    operation_id="get_ticket",
    summary="Get ticket by ID",
    description="Retrieve a ticket by its unique identifier.",
    responses={
        200: {"description": "Ticket retrieved successfully"},
        404: {"description": "Ticket not found"},
    },
)
async def get_ticket_route(
    ticket_id: str = Path(..., examples=["TK-1001"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> TicketResponse:
    ticket = await _call_service(
        get_ticket,
        fallback_args=[
            (ticket_id, db, x_student_id, x_request_id),
            (ticket_id, db, x_student_id),
            (ticket_id, db),
            (ticket_id,),
        ],
        db=db,
        ticket_id=ticket_id,
        id=ticket_id,
        student_id=x_student_id,
        request_id=x_request_id,
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.get(
    "/api/v1/tickets",
    response_model=list[TicketResponse],
    tags=["Tickets"],
    operation_id="list_tickets",
    summary="List tickets",
    description="List tickets with optional filters. Results are automatically scoped by the X-Student-ID header.",
    responses={200: {"description": "Tickets retrieved successfully"}},
)
async def list_tickets_route(
    employee_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    ticket_status: str | None = Query(default=None, alias="status"),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> list[TicketResponse]:
    filters = _build_ticket_filter(employee_id, category, priority, ticket_status, x_student_id)
    tickets = await _call_service(
        list_tickets,
        fallback_args=[
            (filters, db, x_student_id, x_request_id),
            (db, filters, x_student_id, x_request_id),
            (filters, db, x_student_id),
            (db, filters, x_student_id),
            (filters, db),
            (db, filters),
            (filters,),
        ],
        db=db,
        filters=filters,
        ticket_filter=filters,
        student_id=x_student_id,
        request_id=x_request_id,
        employee_id=employee_id,
        category=category,
        priority=priority,
        status=ticket_status,
    )
    ticket_list = list(tickets or [])
    return [
        ticket
        for ticket in ticket_list
        if _matches_filter(ticket, ("student_id", "requester_student_id", "created_by_student_id"), x_student_id)
        and _matches_filter(ticket, ("employee_id",), employee_id)
        and _matches_filter(ticket, ("category",), category)
        and _matches_filter(ticket, ("priority",), priority)
        and _matches_filter(ticket, ("status",), ticket_status)
    ]
