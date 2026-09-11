from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.seed import get_student
from ...models.approval_request import ApprovalDecision, ApprovalRequestCreate, ApprovalRequestResponse
from ...services.approval_service import create_approval_request, decide_approval_request, get_approval_request
from ...services.audit_service import create_event


router = APIRouter()


@router.post(
    "/api/v1/approval-requests",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Approval Requests"],
    operation_id="create_approval_request",
    summary="Create approval request",
    description="Create a fictional approval request for sensitive academic actions.",
)
async def create_approval_request_route(
    approval_data: ApprovalRequestCreate = Body(
        ...,
        openapi_examples={
            "sensitive_request": {
                "summary": "Sensitive academic action",
                "value": {
                    "student_id": "STU001",
                    "request_type": "visitor_campus_authorization",
                    "justification": "Fictional didactic request that requires review by a human approver in the lab.",
                    "risk": "high",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> ApprovalRequestResponse:
    if get_student(approval_data.student_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    approval_request = create_approval_request(db=db, payload=approval_data, lab_student_id=x_student_id)
    _ = create_event(
        db=db,
        event_type="approval_requested",
        student_id=x_student_id,
        fictional_student_id=approval_request.student_id,
        resource_type="approval_request",
        resource_id=approval_request.approval_id,
        metadata={"request_id": x_request_id, "risk": approval_request.risk, "status": approval_request.status},
    )
    return approval_request


@router.get(
    "/api/v1/approval-requests/{approval_id}",
    response_model=ApprovalRequestResponse,
    tags=["Approval Requests"],
    operation_id="get_approval_request",
    summary="Get approval request",
    description="Retrieve a fictional approval request by ID.",
    responses={404: {"description": "Approval request not found"}},
)
async def get_approval_request_route(
    approval_id: str = Path(..., examples=["APR-501"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> ApprovalRequestResponse:
    _ = x_request_id
    approval_request = get_approval_request(db=db, approval_id=approval_id)
    if approval_request is None or approval_request.lab_student_id != x_student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    return approval_request


@router.post(
    "/api/v1/approval-requests/{approval_id}/decision",
    response_model=ApprovalRequestResponse,
    tags=["Approval Requests"],
    operation_id="decide_approval_request",
    summary="Approve or reject approval request",
    description="Apply a human decision to a pending approval request.",
    responses={404: {"description": "Approval request not found"}, 400: {"description": "Approval request cannot be decided"}},
)
async def decide_approval_request_route(
    approval_id: str = Path(..., examples=["APR-501"]),
    decision_data: ApprovalDecision = Body(...),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> ApprovalRequestResponse:
    existing_request = get_approval_request(db=db, approval_id=approval_id)
    if existing_request is None or existing_request.lab_student_id != x_student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    try:
        approval_request = decide_approval_request(db=db, approval_id=approval_id, decision=decision_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _ = create_event(
        db=db,
        event_type="approval_approved" if decision_data.decision == "approve" else "approval_rejected",
        student_id=x_student_id,
        fictional_student_id=approval_request.student_id,
        resource_type="approval_request",
        resource_id=approval_request.approval_id,
        metadata={"request_id": x_request_id, "decision": decision_data.decision, "approved_by": decision_data.approved_by},
    )
    return approval_request
