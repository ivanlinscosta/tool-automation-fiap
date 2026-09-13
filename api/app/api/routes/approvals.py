from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.approval import Approval, ApprovalCreate, ApprovalDecision, ApprovalDetail, ApprovalResponse
from ...services.audit_service import create_event
from ...services.idempotency_service import IdempotencyConflictError, mark_applied, replay_or_none


router = APIRouter()


def _get_approval_or_404(db: Session, approval_id: str, lab_group: str) -> Approval:
    approval = db.execute(
        select(Approval).where(Approval.approval_id == approval_id, Approval.lab_group == lab_group)
    ).scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    return approval


def _next_approval_number(db: Session) -> int:
    approval_ids = db.execute(select(Approval.approval_id)).scalars().all()
    numbers = [int(approval_id.split("-")[-1]) for approval_id in approval_ids]
    return max(numbers, default=0) + 1


@router.post(
    "/api/v1/approvals",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Approvals"],
    operation_id="create_approval",
)
async def create_approval(
    payload: ApprovalCreate,
    request: Request,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ApprovalResponse | JSONResponse:
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        try:
            replay = replay_or_none(db, idem_key, x_lab_group, "approval")
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
        if replay:
            existing = db.get(Approval, replay.resource_id)
            if existing and existing.lab_group == x_lab_group:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=ApprovalResponse.model_validate(existing).model_dump(mode="json"),
                )

    approval = Approval(
        approval_id=f"APR-{_next_approval_number(db)}",
        type=payload.type,
        reference_id=payload.reference_id,
        requested_by=payload.requested_by,
        amount=payload.amount,
        reason=payload.reason,
        status="pending",
        decision=None,
        comment=None,
        decided_by=None,
        lab_group=x_lab_group,
        created_at=datetime.now(UTC),
        decided_at=None,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    _ = create_event(
        db=db,
        event_type="approval_requested",
        lab_group=x_lab_group,
        resource_type="approval",
        resource_id=approval.approval_id,
        metadata={"type": approval.type, "reference_id": approval.reference_id, "amount": approval.amount},
    )

    if idem_key:
        mark_applied(db, idem_key, x_lab_group, "approval", approval.approval_id)

    return ApprovalResponse.model_validate(approval)


@router.get(
    "/api/v1/approvals/{approval_id}",
    response_model=ApprovalDetail,
    tags=["Approvals"],
    operation_id="get_approval",
)
async def get_approval(
    approval_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ApprovalDetail:
    approval = _get_approval_or_404(db, approval_id, x_lab_group)
    return ApprovalDetail.model_validate(approval)


@router.post(
    "/api/v1/approvals/{approval_id}/decision",
    response_model=ApprovalDetail,
    tags=["Approvals"],
    operation_id="create_approval_decision",
)
async def create_approval_decision(
    approval_id: str,
    payload: ApprovalDecision,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ApprovalDetail:
    approval = _get_approval_or_404(db, approval_id, x_lab_group)
    if approval.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already decided")

    approval.status = payload.decision
    approval.decision = payload.decision
    approval.comment = payload.comment
    approval.decided_by = "supervisor.ops@quantum.example"
    approval.decided_at = datetime.now(UTC)
    db.add(approval)
    db.commit()
    db.refresh(approval)

    _ = create_event(
        db=db,
        event_type="approval_decision",
        lab_group=x_lab_group,
        resource_type="approval",
        resource_id=approval.approval_id,
        metadata={"decision": approval.decision, "comment": approval.comment},
    )

    return ApprovalDetail.model_validate(approval)
