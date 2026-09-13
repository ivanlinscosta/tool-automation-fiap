from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.customer import Customer
from ...models.product import Product
from ...models.promotion import Promotion, PromotionResponse
from ...services.audit_service import create_event


router = APIRouter()

TODAY = date(2026, 9, 13)


def _active_promotions_query():
    return (
        select(Promotion)
        .where(Promotion.active.is_(True), Promotion.starts_at <= TODAY, Promotion.ends_at >= TODAY)
        .order_by(Promotion.discount_pct.desc(), Promotion.promotion_id.asc())
    )


def _get_promotion_or_404(db: Session, promotion_id: str) -> Promotion:
    promotion = db.execute(select(Promotion).where(Promotion.promotion_id == promotion_id)).scalar_one_or_none()
    if promotion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    return promotion


@router.get(
    "/api/v1/promotions",
    response_model=list[PromotionResponse],
    tags=["Promotions"],
    operation_id="list_active_promotions",
)
async def list_active_promotions(
    country: str | None = Query(default=None),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[PromotionResponse]:
    query = _active_promotions_query()
    if country:
        query = query.where(Promotion.country == country)
    promotions = list(db.execute(query).scalars().all())
    _ = create_event(
        db,
        "promotion_checked",
        x_lab_group,
        "promotion_list",
        country or "all",
        metadata={"country": country, "result_count": len(promotions)},
    )
    return [PromotionResponse.model_validate(promotion) for promotion in promotions]


@router.get(
    "/api/v1/promotions/eligible",
    response_model=list[dict[str, Any]],
    tags=["Promotions"],
    operation_id="get_eligible_promotions",
)
async def get_eligible_promotions(
    customer_id: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    if not customer_id and not sku:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="At least one of customer_id or sku is required")

    customer = None
    if customer_id:
        customer = db.execute(select(Customer).where(Customer.id == customer_id)).scalar_one_or_none()
        if customer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    product = None
    if sku:
        product = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    promotions = list(db.execute(_active_promotions_query()).scalars().all())
    results: list[dict[str, Any]] = []

    for promotion in promotions:
        if product is None and any(value is not None for value in (promotion.category, promotion.brand, promotion.min_price)):
            eligible = False
            reason = "sku_required_for_product_rules"
        elif product is not None and promotion.category is not None and promotion.category != product.category:
            eligible = False
            reason = "category_mismatch"
        elif product is not None and promotion.brand is not None and promotion.brand != product.brand:
            eligible = False
            reason = "brand_mismatch"
        elif customer is None and promotion.country is not None:
            eligible = False
            reason = "customer_required_for_country_rules"
        elif customer is not None and promotion.country is not None and promotion.country != customer.country:
            eligible = False
            reason = "country_mismatch"
        elif product is not None and promotion.min_price is not None and product.price < promotion.min_price:
            eligible = False
            reason = "below_min_price"
        else:
            eligible = True
            reason = "eligible"

        results.append(
            {
                "promotion_id": promotion.promotion_id,
                "name": promotion.name,
                "discount_pct": promotion.discount_pct,
                "eligible": eligible,
                "reason": reason,
            }
        )

    _ = create_event(
        db,
        "promotion_checked",
        x_lab_group,
        "promotion_eligibility",
        customer_id or sku or "eligible",
        metadata={"customer_id": customer_id, "sku": sku, "result_count": len(results)},
        customer_id=customer_id,
    )
    return results


@router.get(
    "/api/v1/promotions/{promotion_id}",
    response_model=PromotionResponse,
    tags=["Promotions"],
    operation_id="get_promotion_by_id",
)
async def get_promotion_by_id(
    promotion_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> PromotionResponse:
    promotion = _get_promotion_or_404(db, promotion_id)
    _ = create_event(
        db,
        "promotion_checked",
        x_lab_group,
        "promotion",
        promotion_id,
    )
    return PromotionResponse.model_validate(promotion)
