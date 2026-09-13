from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.order import Order, OrderItem, OrderResponse
from ...models.shipment import Shipment, ShipmentResponse
from ...services.audit_service import create_event


router = APIRouter()


def _get_order_or_404(db: Session, order_id: str) -> Order:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _get_shipment_by_order_id(db: Session, order_id: str) -> Shipment | None:
    return db.execute(select(Shipment).where(Shipment.order_id == order_id)).scalar_one_or_none()


def _serialize_order(order: Order, items: list[OrderItem]) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status,
        created_at=order.created_at,
        total=order.total,
        currency=order.currency,
        items=[
            {
                "sku": item.sku,
                "name": item.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in items
        ],
    )


@router.get(
    "/api/v1/orders/{order_id}",
    response_model=OrderResponse,
    tags=["Orders"],
    operation_id="get_order_by_id",
)
async def get_order_by_id(
    order_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> OrderResponse:
    order = _get_order_or_404(db, order_id)
    items = list(
        db.execute(
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.id.asc())
        ).scalars().all()
    )
    _ = create_event(
        db,
        "order_lookup",
        x_lab_group,
        "order",
        order_id,
        customer_id=order.customer_id,
    )
    return _serialize_order(order, items)


@router.get(
    "/api/v1/orders/{order_id}/shipment",
    response_model=ShipmentResponse,
    tags=["Orders"],
    operation_id="get_order_shipment",
    responses={404: {"description": "Order or shipment not found"}},
)
async def get_order_shipment(
    order_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    order = _get_order_or_404(db, order_id)
    shipment = _get_shipment_by_order_id(db, order_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    _ = create_event(
        db,
        "shipment_lookup",
        x_lab_group,
        "shipment",
        shipment.shipment_id,
        metadata={"order_id": order_id},
        customer_id=order.customer_id,
    )
    return ShipmentResponse.model_validate(shipment)
