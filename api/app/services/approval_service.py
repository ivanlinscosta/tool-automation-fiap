from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.approval_request import ApprovalDecision, ApprovalRequest, ApprovalRequestCreate


def _next_approval_number(db: Session) -> int:
    existing_ids = db.execute(select(ApprovalRequest.approval_id)).scalars().all()
    max_number = max((int(approval_id.split("-")[-1]) for approval_id in existing_ids), default=500)
    return max_number + 1


def create_approval_request(db: Session, payload: ApprovalRequestCreate, lab_student_id: str) -> ApprovalRequest:
    is_low_risk = payload.risk == "low"
    approval_request = ApprovalRequest(
        approval_id=f"APR-{_next_approval_number(db)}",
        student_id=payload.student_id,
        request_type=payload.request_type,
        justification=payload.justification,
        risk=payload.risk,
        status="auto_approved" if is_low_risk else "pending_human_approval",
        requires_human_approval=not is_low_risk,
        approved_by="system" if is_low_risk else None,
        decision="auto_approved" if is_low_risk else None,
        decision_comment="Automatically approved by didactic low-risk policy." if is_low_risk else None,
        decision_at=datetime.now(UTC) if is_low_risk else None,
        lab_student_id=lab_student_id,
        created_at=datetime.now(UTC),
    )
    db.add(approval_request)
    db.commit()
    db.refresh(approval_request)
    return approval_request


def get_approval_request(db: Session, approval_id: str) -> ApprovalRequest | None:
    return db.get(ApprovalRequest, approval_id)


def decide_approval_request(db: Session, approval_id: str, decision: ApprovalDecision) -> ApprovalRequest:
    approval_request = db.get(ApprovalRequest, approval_id)
    if approval_request is None:
        raise ValueError(f"Approval request {approval_id} not found")

    if approval_request.status != "pending_human_approval":
        raise ValueError(f"Approval request {approval_id} is not pending human approval")

    approval_request.status = "approved" if decision.decision == "approve" else "rejected"
    approval_request.approved_by = decision.approved_by
    approval_request.decision = decision.decision
    approval_request.decision_comment = decision.comment
    approval_request.decision_at = datetime.now(UTC)

    db.add(approval_request)
    db.commit()
    db.refresh(approval_request)
    return approval_request
