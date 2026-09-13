from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...db.database import get_db
from ...models.approval import Approval
from ...models.refund import Refund, RefundCreate, RefundResponse
from ...services.audit_service import create_event
from ...services.idempotency_service import IdempotencyConflictError, mark_applied, replay_or_none


router = APIRouter()


def _get_refund_or_404(db: Session, refund_id: str, lab_group: str) -> Refund:
    refund = db.execute(select(Refund).where(Refund.refund_id == refund_id, Refund.lab_group == lab_group)).scalar_one_or_none()
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found")
    return refund


def _next_refund_number(db: Session) -> int:
    refund_ids = db.execute(select(Refund.refund_id)).scalars().all()
    numbers = [int(refund_id.split("-")[-1]) for refund_id in refund_ids]
    return max(numbers, default=0) + 1


def _serialize_refund(refund: Refund) -> dict[str, Any]:
    return {
        "refund_id": refund.refund_id,
        "order_id": refund.order_id,
        "amount": refund.amount,
        "reason": refund.reason,
        "approval_id": refund.approval_id,
        "status": refund.status,
        "lab_group": refund.lab_group,
        "created_at": refund.created_at,
    }


def _require_approved_high_value_refund(db: Session, approval_id: str | None, lab_group: str) -> Approval:
    message = f"Refunds above R${settings.REFUND_APPROVAL_THRESHOLD:.2f} require an approved approval"
    if not approval_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    approval = db.execute(
        select(Approval).where(Approval.approval_id == approval_id, Approval.lab_group == lab_group)
    ).scalar_one_or_none()
    if approval is None or approval.status != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return approval


@router.post(
    "/api/v1/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Refunds"],
    operation_id="create_refund",
)
async def create_refund(
    payload: RefundCreate,
    request: Request,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> RefundResponse | JSONResponse:
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        try:
            replay = replay_or_none(db, idem_key, x_lab_group, "refund")
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
        if replay:
            existing = db.get(Refund, replay.resource_id)
            if existing and existing.lab_group == x_lab_group:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=RefundResponse.model_validate(existing).model_dump(mode="json"),
                )

    if payload.amount > settings.REFUND_APPROVAL_THRESHOLD:
        _require_approved_high_value_refund(db, payload.approval_id, x_lab_group)

    _ = create_event(
        db=db,
        event_type="refund_requested",
        lab_group=x_lab_group,
        resource_type="refund_request",
        resource_id=payload.order_id,
        metadata={"amount": payload.amount, "approval_id": payload.approval_id},
    )

    refund = Refund(
        refund_id=f"REF-{_next_refund_number(db)}",
        order_id=payload.order_id,
        amount=payload.amount,
        reason=payload.reason,
        approval_id=payload.approval_id,
        status="processing",
        lab_group=x_lab_group,
        created_at=datetime.now(UTC),
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)

    _ = create_event(
        db=db,
        event_type="refund_created",
        lab_group=x_lab_group,
        resource_type="refund",
        resource_id=refund.refund_id,
        metadata={"order_id": refund.order_id, "amount": refund.amount, "approval_id": refund.approval_id},
    )

    if idem_key:
        mark_applied(db, idem_key, x_lab_group, "refund", refund.refund_id)

    return RefundResponse.model_validate(refund)


@router.get(
    "/api/v1/refunds/{refund_id}",
    response_model=dict,
    tags=["Refunds"],
    operation_id="get_refund",
)
async def get_refund(
    refund_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    refund = _get_refund_or_404(db, refund_id, x_lab_group)
    return _serialize_refund(refund)
