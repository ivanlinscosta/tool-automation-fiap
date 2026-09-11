from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, Body, Header

from app.models.priority import PriorityRequest, PriorityResponse
from app.services.priority_service import calculate_priority


router = APIRouter()


async def _call_calculate_priority(
    priority_request: PriorityRequest,
    student_id: str,
    request_id: str,
) -> Any:
    signature = inspect.signature(calculate_priority)
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    candidate_kwargs = {
        "priority_request": priority_request,
        "request": priority_request,
        "payload": priority_request,
        "student_id": student_id,
        "request_id": request_id,
    }
    supported_kwargs = (
        candidate_kwargs
        if accepts_kwargs
        else {key: value for key, value in candidate_kwargs.items() if key in signature.parameters}
    )

    if supported_kwargs:
        result = calculate_priority(**supported_kwargs)
    else:
        result = calculate_priority(priority_request)

    if inspect.isawaitable(result):
        return await result
    return result


@router.post(
    "/api/v1/priority/check",
    response_model=PriorityResponse,
    tags=["Priority"],
    operation_id="check_priority",
    summary="Check ticket priority",
    description="Deterministic priority calculation based on employee, category, impact and urgency",
    responses={
        200: {"description": "Priority calculated successfully"},
        422: {"description": "Validation error"},
    },
)
async def check_priority(
    priority_request: PriorityRequest = Body(
        ...,
        openapi_examples={
            "critical_access_issue": {
                "summary": "Critical IT access issue",
                "value": {
                    "employee_id": "EMP001",
                    "category": "it",
                    "impact": "high",
                    "urgency": "high",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> PriorityResponse:
    return await _call_calculate_priority(priority_request, x_student_id, x_request_id)
