from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.customer import Customer, CustomerContextResponse, CustomerResponse, RecommendationContextResponse
from ...models.order import Order, OrderItem, OrderResponse
from ...models.product import Product
from ...models.return_record import ReturnRecord
from ...models.support_case import SupportCase
from ...services.audit_service import create_event


router = APIRouter()

OPEN_ORDER_STATUSES = {"pending", "confirmed", "awaiting_pickup", "shipped", "in_transit"}
OPEN_SUPPORT_CASE_STATUSES = {"open", "in_progress", "waiting_customer"}


def _get_customer_or_404(db: Session, customer_id: str) -> Customer:
    customer = db.execute(select(Customer).where(Customer.id == customer_id)).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def _serialize_order(order: Order, items_by_order_id: dict[str, list[OrderItem]]) -> OrderResponse:
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
            for item in items_by_order_id.get(order.id, [])
        ],
    )


@router.get(
    "/api/v1/customers/search",
    response_model=list[CustomerResponse],
    tags=["Customers"],
    operation_id="search_customers",
)
async def search_customers(
    email: str | None = Query(default=None),
    name: str | None = Query(default=None),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[CustomerResponse]:
    query = select(Customer)
    if email:
        query = query.where(Customer.email.ilike(f"%{email}%"))
    if name:
        query = query.where(Customer.name.ilike(f"%{name}%"))
    customers = list(db.execute(query.order_by(Customer.name.asc()).limit(100)).scalars().all())
    _ = create_event(
        db,
        "customer_lookup",
        x_lab_group,
        "customer_search",
        "search",
        metadata={"email": email, "name": name, "result_count": len(customers)},
    )
    return [CustomerResponse.model_validate(customer) for customer in customers]


@router.get(
    "/api/v1/customers/{customer_id}",
    response_model=CustomerResponse,
    tags=["Customers"],
    operation_id="get_customer_by_id",
)
async def get_customer_by_id(
    customer_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> CustomerResponse:
    customer = _get_customer_or_404(db, customer_id)
    _ = create_event(
        db,
        "customer_lookup",
        x_lab_group,
        "customer",
        customer_id,
        customer_id=customer_id,
    )
    return CustomerResponse.model_validate(customer)


@router.get(
    "/api/v1/customers/{customer_id}/context",
    response_model=CustomerContextResponse,
    tags=["Customers"],
    operation_id="get_customer_context",
)
async def get_customer_context(
    customer_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> CustomerContextResponse:
    customer = _get_customer_or_404(db, customer_id)
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=365)

    open_orders = db.execute(
        select(func.count())
        .select_from(Order)
        .where(Order.customer_id == customer_id, Order.status.in_(OPEN_ORDER_STATUSES))
    ).scalar_one()
    open_support_cases = db.execute(
        select(func.count())
        .select_from(SupportCase)
        .where(SupportCase.customer_id == customer_id, SupportCase.status.in_(OPEN_SUPPORT_CASE_STATUSES))
    ).scalar_one()
    returns_last_12_months = db.execute(
        select(func.count())
        .select_from(ReturnRecord)
        .where(ReturnRecord.customer_id == customer_id, ReturnRecord.created_at > since)
    ).scalar_one()

    _ = create_event(
        db,
        "customer_lookup",
        x_lab_group,
        "customer_context",
        customer_id,
        customer_id=customer_id,
    )

    return CustomerContextResponse(
        customer_id=customer.id,
        segment=customer.segment,
        loyalty_tier=customer.loyalty_tier,
        total_orders=customer.total_orders,
        open_orders=open_orders,
        open_support_cases=open_support_cases,
        returns_last_12_months=returns_last_12_months,
        lifetime_value=customer.lifetime_value,
    )


@router.get(
    "/api/v1/customers/{customer_id}/orders",
    response_model=list[OrderResponse],
    tags=["Customers"],
    operation_id="get_customer_orders",
)
async def get_customer_orders(
    customer_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[OrderResponse]:
    _get_customer_or_404(db, customer_id)

    query = select(Order).where(Order.customer_id == customer_id)
    if status_filter:
        query = query.where(Order.status == status_filter)
    orders = list(db.execute(query.order_by(Order.created_at.desc()).limit(limit)).scalars().all())

    items_by_order_id: dict[str, list[OrderItem]] = {}
    if orders:
        order_ids = [order.id for order in orders]
        order_items = list(db.execute(select(OrderItem).where(OrderItem.order_id.in_(order_ids))).scalars().all())
        for item in order_items:
            items_by_order_id.setdefault(item.order_id, []).append(item)

    _ = create_event(
        db,
        "order_lookup",
        x_lab_group,
        "customer_orders",
        customer_id,
        metadata={"status": status_filter, "limit": limit, "result_count": len(orders)},
        customer_id=customer_id,
    )
    return [_serialize_order(order, items_by_order_id) for order in orders]


@router.get(
    "/api/v1/customers/{customer_id}/recommendation-context",
    response_model=RecommendationContextResponse,
    tags=["Customers"],
    operation_id="get_customer_recommendation_context",
)
async def get_customer_recommendation_context(
    customer_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> RecommendationContextResponse:
    _get_customer_or_404(db, customer_id)

    recent_categories = list(
        db.execute(
            select(Product.category)
            .join(OrderItem, OrderItem.sku == Product.sku)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.customer_id == customer_id)
            .group_by(Product.category)
            .order_by(func.count().desc(), Product.category.asc())
            .limit(3)
        ).scalars().all()
    )
    recent_products = list(
        db.execute(
            select(OrderItem.sku)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc(), OrderItem.id.desc())
            .limit(5)
        ).scalars().all()
    )
    preferred_brands = list(
        db.execute(
            select(Product.brand)
            .join(OrderItem, OrderItem.sku == Product.sku)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.customer_id == customer_id)
            .group_by(Product.brand)
            .order_by(func.count().desc(), Product.brand.asc())
            .limit(3)
        ).scalars().all()
    )
    average_order_value = db.execute(
        select(func.avg(Order.total)).where(Order.customer_id == customer_id)
    ).scalar_one()
    average_order_value = float(average_order_value or 0.0)

    if average_order_value > 1000:
        price_sensitivity = "low"
    elif average_order_value > 300:
        price_sensitivity = "medium"
    else:
        price_sensitivity = "high"

    _ = create_event(
        db,
        "customer_lookup",
        x_lab_group,
        "recommendation_context",
        customer_id,
        customer_id=customer_id,
    )

    return RecommendationContextResponse(
        customer_id=customer_id,
        recent_categories=recent_categories,
        recent_products=recent_products,
        preferred_brands=preferred_brands,
        average_order_value=average_order_value,
        price_sensitivity=price_sensitivity,
    )
