from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.support_case import (
    PriorityCheckRequest,
    SupportCase,
    SupportCaseCreate,
    SupportCaseDetail,
    SupportCaseResponse,
)
from ...services.audit_service import create_event
from ...services.idempotency_service import IdempotencyConflictError, mark_applied, replay_or_none


router = APIRouter()


def _get_support_case_or_404(db: Session, case_id: str, lab_group: str) -> SupportCase:
    support_case = db.execute(
        select(SupportCase).where(SupportCase.case_id == case_id, SupportCase.lab_group == lab_group)
    ).scalar_one_or_none()
    if support_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support case not found")
    return support_case


def _next_case_number(db: Session) -> int:
    case_ids = db.execute(select(SupportCase.case_id)).scalars().all()
    numbers = [int(case_id.rsplit("-", maxsplit=1)[-1]) for case_id in case_ids]
    return max(numbers, default=0) + 1


def _classify_priority(payload: PriorityCheckRequest) -> dict[str, int | str]:
    impact = payload.impact.strip().lower()
    urgency = payload.urgency.strip().lower()

    if impact == "high" and urgency == "high":
        priority = "P1"
        sla_hours = 2
    elif (impact == "high" and urgency == "medium") or (impact == "medium" and urgency == "high"):
        priority = "P2"
        sla_hours = 4
    elif (impact == "medium" and urgency == "medium") or (impact == "high" and urgency == "low") or (impact == "low" and urgency == "high"):
        priority = "P3"
        sla_hours = 8
    else:
        priority = "P4"
        sla_hours = 24

    rationale = (
        f"Category '{payload.category}' was classified as {priority} because impact is {impact} "
        f"and urgency is {urgency}, resulting in an SLA of {sla_hours} hours."
    )
    return {"priority": priority, "sla_hours": sla_hours, "rationale": rationale}


@router.post(
    "/api/v1/support/cases",
    response_model=SupportCaseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Support"],
    operation_id="create_support_case",
)
async def create_support_case(
    payload: SupportCaseCreate,
    request: Request,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> SupportCaseResponse | JSONResponse:
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        try:
            replay = replay_or_none(db, idem_key, x_lab_group, "support_case")
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
        if replay:
            existing = db.get(SupportCase, replay.resource_id)
            if existing and existing.lab_group == x_lab_group:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=SupportCaseResponse.model_validate(existing).model_dump(mode="json"),
                )

    priority_result = _classify_priority(
        PriorityCheckRequest(category=payload.category, impact="medium", urgency="medium")
    )
    case_number = _next_case_number(db)
    support_case = SupportCase(
        case_id=f"CASE-2026-{case_number}",
        protocol=f"QCS-{case_number}",
        customer_id=payload.customer_id,
        category=payload.category,
        summary=payload.summary,
        description=payload.description,
        status="open",
        priority=str(priority_result["priority"]),
        lab_group=x_lab_group,
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    db.add(support_case)
    db.commit()
    db.refresh(support_case)

    _ = create_event(
        db=db,
        event_type="support_case_created",
        lab_group=x_lab_group,
        resource_type="support_case",
        resource_id=support_case.case_id,
        metadata={"priority": support_case.priority, "protocol": support_case.protocol},
        customer_id=support_case.customer_id,
    )

    if idem_key:
        mark_applied(db, idem_key, x_lab_group, "support_case", support_case.case_id)

    return SupportCaseResponse.model_validate(support_case)


@router.get(
    "/api/v1/support/cases/{case_id}",
    response_model=SupportCaseDetail,
    tags=["Support"],
    operation_id="get_support_case",
)
async def get_support_case(
    case_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> SupportCaseDetail:
    support_case = _get_support_case_or_404(db, case_id, x_lab_group)
    return SupportCaseDetail.model_validate(support_case)


@router.get(
    "/api/v1/customers/{customer_id}/support-cases",
    response_model=list[SupportCaseDetail],
    tags=["Support"],
    operation_id="list_customer_support_cases",
)
async def list_customer_support_cases(
    customer_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[SupportCaseDetail]:
    support_cases = list(
        db.execute(
            select(SupportCase)
            .where(SupportCase.customer_id == customer_id, SupportCase.lab_group == x_lab_group)
            .order_by(SupportCase.created_at.desc(), SupportCase.case_id.desc())
        ).scalars().all()
    )
    _ = create_event(
        db=db,
        event_type="support_case_created",
        lab_group=x_lab_group,
        resource_type="support_case",
        resource_id="list",
        metadata={"customer_id": customer_id, "result_count": len(support_cases)},
        customer_id=customer_id,
    )
    return [SupportCaseDetail.model_validate(support_case) for support_case in support_cases]


@router.post(
    "/api/v1/support/priority/check",
    response_model=dict,
    tags=["Support"],
    operation_id="check_support_priority",
)
async def check_support_priority(
    payload: PriorityCheckRequest,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    result = _classify_priority(payload)
    _ = create_event(
        db=db,
        event_type="priority_checked",
        lab_group=x_lab_group,
        resource_type="support_priority",
        resource_id=payload.category,
        metadata={
            "category": payload.category,
            "impact": payload.impact,
            "urgency": payload.urgency,
            "priority": result["priority"],
            "sla_hours": result["sla_hours"],
        },
    )
    return result
