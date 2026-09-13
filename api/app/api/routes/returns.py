from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.customer import Customer
from ...models.order import Order, OrderItem
from ...models.return_record import ReturnCreate, ReturnEligibilityRequest, ReturnEligibilityResponse, ReturnRecord, ReturnResponse
from ...models.shipment import Shipment
from ...services.audit_service import create_event
from ...services.idempotency_service import IdempotencyConflictError, mark_applied, replay_or_none


router = APIRouter()

TODAY = date(2026, 9, 13)
RETURN_WINDOW_BY_COUNTRY = {"BR": 30, "MX": 30, "AR": 10, "CO": 15, "CL": 30, "PT": 14, "US": 30}


def _get_order(db: Session, order_id: str) -> Order | None:
    return db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()


def _get_shipment_for_order(db: Session, order_id: str) -> Shipment | None:
    return db.execute(select(Shipment).where(Shipment.order_id == order_id)).scalar_one_or_none()


def _get_return_or_404(db: Session, return_id: str) -> ReturnRecord:
    return_record = db.execute(select(ReturnRecord).where(ReturnRecord.return_id == return_id)).scalar_one_or_none()
    if return_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")
    return return_record


def _serialize_return_record(return_record: ReturnRecord) -> dict[str, Any]:
    return {
        "return_id": return_record.return_id,
        "protocol": return_record.protocol,
        "customer_id": return_record.customer_id,
        "order_id": return_record.order_id,
        "sku": return_record.sku,
        "reason": return_record.reason,
        "status": return_record.status,
        "lab_group": return_record.lab_group,
        "created_at": return_record.created_at.isoformat(),
    }


def _extract_return_number(return_id: str) -> int:
    try:
        return int(return_id.split("-", maxsplit=1)[1])
    except (IndexError, ValueError):
        return 0


def _next_return_number(db: Session) -> int:
    return_ids = list(db.execute(select(ReturnRecord.return_id)).scalars().all())
    return max((_extract_return_number(return_id) for return_id in return_ids), default=0) + 1


def _delivered_date_from_events(events: list[dict[str, Any]] | None) -> date | None:
    for event in events or []:
        if event.get("status") != "delivered":
            continue
        timestamp = event.get("timestamp")
        if isinstance(timestamp, datetime):
            return timestamp.date()
        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
            except ValueError:
                return None
    return None


@router.post(
    "/api/v1/returns/check-eligibility",
    response_model=ReturnEligibilityResponse,
    tags=["Returns"],
    operation_id="check_return_eligibility",
)
async def check_return_eligibility(
    payload: ReturnEligibilityRequest,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ReturnEligibilityResponse:
    order = _get_order(db, payload.order_id)
    if order is None:
        response = ReturnEligibilityResponse(
            eligible=False,
            reason="order_not_found",
            return_window_days=0,
        )
        _ = create_event(
            db,
            "return_eligibility_checked",
            x_lab_group,
            "return_eligibility",
            payload.order_id,
            metadata={"sku": payload.sku, **response.model_dump(mode="json")},
        )
        return response

    shipment = _get_shipment_for_order(db, payload.order_id)
    customer = db.execute(select(Customer).where(Customer.id == order.customer_id)).scalar_one_or_none()
    return_window_days = RETURN_WINDOW_BY_COUNTRY.get(customer.country if customer else "", 30)

    delivered_date = _delivered_date_from_events(shipment.events if shipment else None)
    order_items = list(db.execute(select(OrderItem).where(OrderItem.order_id == payload.order_id)).scalars().all())

    if delivered_date is None:
        response = ReturnEligibilityResponse(
            eligible=False,
            reason="order_not_delivered",
            return_window_days=return_window_days,
        )
    elif not any(item.sku == payload.sku for item in order_items):
        response = ReturnEligibilityResponse(
            eligible=False,
            reason="product_not_in_order",
            return_window_days=return_window_days,
        )
    else:
        days_since_delivery = (TODAY - delivered_date).days
        if days_since_delivery <= 0:
            response = ReturnEligibilityResponse(
                eligible=False,
                reason="order_not_delivered",
                days_since_delivery=days_since_delivery,
                return_window_days=return_window_days,
            )
        elif days_since_delivery > return_window_days:
            response = ReturnEligibilityResponse(
                eligible=False,
                reason="outside_return_window",
                days_since_delivery=days_since_delivery,
                return_window_days=return_window_days,
            )
        else:
            response = ReturnEligibilityResponse(
                eligible=True,
                reason="within_return_window",
                days_since_delivery=days_since_delivery,
                return_window_days=return_window_days,
                policy_id="POL-RETURN-001",
            )

    _ = create_event(
        db,
        "return_eligibility_checked",
        x_lab_group,
        "return_eligibility",
        payload.order_id,
        metadata={"sku": payload.sku, **response.model_dump(mode="json")},
        customer_id=order.customer_id,
    )
    return response


@router.post(
    "/api/v1/returns",
    response_model=ReturnResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Returns"],
    operation_id="create_return",
    responses={200: {"description": "Idempotent replay"}, 404: {"description": "Order not found"}, 409: {"description": "Idempotency key conflict"}},
)
async def create_return(
    payload: ReturnCreate,
    request: Request,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ReturnResponse | JSONResponse:
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        try:
            replay = replay_or_none(db, idem_key, x_lab_group, "return")
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
        if replay:
            existing = db.execute(
                select(ReturnRecord).where(ReturnRecord.return_id == replay.resource_id)
            ).scalar_one_or_none()
            if existing:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=ReturnResponse.model_validate(existing).model_dump(mode="json"),
                )

    order = _get_order(db, payload.order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    next_number = _next_return_number(db)
    return_id = f"RET-{next_number}"
    protocol = f"QRET-2026-{next_number}"
    return_record = ReturnRecord(
        return_id=return_id,
        protocol=protocol,
        customer_id=payload.customer_id,
        order_id=payload.order_id,
        sku=payload.sku,
        reason=payload.reason,
        status="requested",
        lab_group=x_lab_group,
        created_at=datetime(2026, 9, 13),
    )
    db.add(return_record)
    db.commit()
    db.refresh(return_record)

    if idem_key:
        _ = mark_applied(db, idem_key, x_lab_group, "return", return_record.return_id)

    _ = create_event(
        db,
        "return_created",
        x_lab_group,
        "return",
        return_record.return_id,
        metadata={"order_id": payload.order_id, "sku": payload.sku, "protocol": protocol},
        customer_id=payload.customer_id,
    )
    return ReturnResponse.model_validate(return_record)


@router.get(
    "/api/v1/returns/{return_id}",
    response_model=dict[str, Any],
    tags=["Returns"],
    operation_id="get_return_by_id",
    responses={404: {"description": "Return not found"}},
)
async def get_return_by_id(
    return_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return_record = _get_return_or_404(db, return_id)
    _ = x_lab_group
    return _serialize_return_record(return_record)


@router.get(
    "/api/v1/customers/{customer_id}/returns",
    response_model=list[dict[str, Any]],
    tags=["Returns"],
    operation_id="list_customer_returns",
)
async def list_customer_returns(
    customer_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    returns = list(
        db.execute(
            select(ReturnRecord)
            .where(ReturnRecord.customer_id == customer_id)
            .order_by(ReturnRecord.created_at.desc(), ReturnRecord.return_id.desc())
        ).scalars().all()
    )
    _ = create_event(
        db,
        "return_eligibility_checked",
        x_lab_group,
        "return",
        "list",
        metadata={"customer_id": customer_id, "result_count": len(returns)},
        customer_id=customer_id,
    )
    return [_serialize_return_record(return_record) for return_record in returns]
