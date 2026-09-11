from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access_request import AccessRequest, AccessRequestApproval, AccessRequestCreate


def _generate_request_id(db: Session) -> str:
    existing_ids = db.execute(select(AccessRequest.request_id)).scalars().all()
    max_number = max((int(request_id.split("-")[-1]) for request_id in existing_ids), default=500)
    return f"AR-{max_number + 1}"


def create_access_request(db: Session, payload: AccessRequestCreate, student_id: str) -> AccessRequest:
    requires_human_approval = payload.risk in {"medium", "high"}

    if payload.risk == "low":
        status = "auto_approved"
        approved_by = "system"
        decision = "auto_approved"
        decision_comment = "Automatically approved by didactic low-risk policy."
        decision_at = datetime.utcnow()
    else:
        status = "pending_approval"
        approved_by = None
        decision = None
        decision_comment = None
        decision_at = None

    access_request = AccessRequest(
        request_id=_generate_request_id(db),
        employee_id=payload.employee_id,
        resource=payload.resource,
        justification=payload.justification,
        risk=payload.risk,
        status=status,
        requires_human_approval=requires_human_approval,
        approved_by=approved_by,
        decision=decision,
        decision_comment=decision_comment,
        decision_at=decision_at,
        student_id=student_id,
        created_at=datetime.utcnow(),
    )
    db.add(access_request)
    db.commit()
    db.refresh(access_request)
    return access_request


def get_access_request_by_id(db: Session, request_id: str) -> AccessRequest | None:
    return db.get(AccessRequest, request_id)


def get_access_request(db: Session, request_id: str) -> AccessRequest | None:
    return get_access_request_by_id(db, request_id)


def review_access_request(db: Session, request_id: str, approval: AccessRequestApproval) -> AccessRequest:
    access_request = get_access_request_by_id(db, request_id)
    if access_request is None:
        raise ValueError(f"Access request {request_id} not found")

    if access_request.status != "pending_approval":
        raise ValueError(f"Access request {request_id} is not pending approval")

    access_request.status = approval.decision
    access_request.approved_by = approval.approved_by
    access_request.decision = approval.decision
    access_request.decision_comment = approval.decision_comment
    access_request.decision_at = datetime.utcnow()

    db.add(access_request)
    db.commit()
    db.refresh(access_request)
    return access_request


def approve_access_request(db: Session, request_id: str, approval: AccessRequestApproval) -> AccessRequest:
    return review_access_request(db, request_id, approval)
