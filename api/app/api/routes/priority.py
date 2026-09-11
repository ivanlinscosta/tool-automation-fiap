from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.priority import PriorityRequest, PriorityResponse
from ...services.audit_service import create_event
from ...services.priority_service import calculate_priority


router = APIRouter()


@router.post(
    "/api/v1/priority/check",
    response_model=PriorityResponse,
    tags=["Priority"],
    operation_id="check_priority",
    summary="Check request priority",
    description="Deterministic priority calculation based on fictional student, category, impact and urgency.",
    responses={
        200: {"description": "Priority calculated successfully"},
        422: {"description": "Validation error"},
    },
)
async def check_priority(
    priority_request: PriorityRequest = Body(
        ...,
        openapi_examples={
            "campus_access_issue": {
                "summary": "Campus access issue with escalation",
                "value": {
                    "student_id": "STU001",
                    "category": "campus_access",
                    "impact": "high",
                    "urgency": "high",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> PriorityResponse:
    result = calculate_priority(priority_request)
    _ = create_event(
        db=db,
        event_type="priority_checked",
        student_id=x_student_id,
        fictional_student_id=priority_request.student_id,
        resource_type="priority_check",
        resource_id=x_request_id,
        metadata={
            "category": priority_request.category,
            "impact": priority_request.impact,
            "urgency": priority_request.urgency,
            "priority": result.priority,
            "rule": result.rule,
        },
    )
    return result
