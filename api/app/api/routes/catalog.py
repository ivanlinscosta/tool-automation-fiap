from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.inventory import InventoryItem
from ...models.product import CatalogStatsResponse, Product, ProductResponse
from ...services.audit_service import create_event


router = APIRouter()


@router.get(
    "/api/v1/products/search",
    response_model=list[ProductResponse],
    tags=["Products"],
    operation_id="search_products",
)
async def search_products_route(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    min_price: float | None = Query(default=None),
    max_price: float | None = Query(default=None),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[ProductResponse]:
    query = select(Product)
    if q:
        query = query.where(Product.name.ilike(f"%{q}%"))
    if category:
        query = query.where(Product.category == category)
    if brand:
        query = query.where(Product.brand == brand)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)

    products = list(db.execute(query.order_by(Product.sku)).scalars().all())
    _ = create_event(
        db=db,
        event_type="product_lookup",
        lab_group=x_lab_group,
        resource_type="product",
        resource_id="search",
        metadata={
            "q": q,
            "category": category,
            "brand": brand,
            "min_price": min_price,
            "max_price": max_price,
            "results": len(products),
        },
    )
    return [ProductResponse.model_validate(product) for product in products]


@router.get(
    "/api/v1/catalog/stats",
    response_model=CatalogStatsResponse,
    tags=["Products"],
    operation_id="get_catalog_stats",
)
async def get_catalog_stats_route(
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> CatalogStatsResponse:
    total_skus = db.execute(select(func.count(Product.sku))).scalar_one()
    active_skus = db.execute(select(func.count(Product.sku)).where(Product.active.is_(True))).scalar_one()
    categories = db.execute(select(func.count(distinct(Product.category)))).scalar_one()
    countries = db.execute(select(func.count(distinct(InventoryItem.country)))).scalar_one()

    _ = create_event(
        db=db,
        event_type="product_lookup",
        lab_group=x_lab_group,
        resource_type="catalog",
        resource_id="stats",
        metadata={
            "total_skus": total_skus,
            "active_skus": active_skus,
            "categories": categories,
            "countries": countries,
        },
    )

    return CatalogStatsResponse(
        total_skus=total_skus,
        active_skus=active_skus,
        categories=categories,
        countries=countries,
    )


@router.get(
    "/api/v1/products/{sku}",
    response_model=ProductResponse,
    tags=["Products"],
    operation_id="get_product",
)
async def get_product_route(
    sku: str = Path(...),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ProductResponse:
    product = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
    _ = create_event(
        db=db,
        event_type="product_lookup",
        lab_group=x_lab_group,
        resource_type="product",
        resource_id=sku,
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductResponse.model_validate(product)
