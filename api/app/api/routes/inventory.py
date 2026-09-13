from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.inventory import AvailabilityResponse, InventoryItem, InventoryResponse, WarehouseStock
from ...models.product import Product
from ...services.audit_service import create_event


router = APIRouter()

_POSTAL_WAREHOUSE_MAP: dict[str, tuple[str, int]] = {
    "0": ("BR-SP-01", 2),
    "2": ("BR-RJ-01", 3),
    "3": ("BR-MG-01", 4),
    "9": ("BR-RS-01", 5),
}


def _get_delivery_mapping(postal_code: str) -> tuple[str, int]:
    if postal_code and postal_code[0].isdigit():
        return _POSTAL_WAREHOUSE_MAP.get(postal_code[0], ("BR-SP-01", 3))
    return ("BR-SP-01", 12)


@router.get(
    "/api/v1/inventory/{sku}",
    response_model=InventoryResponse,
    tags=["Inventory"],
    operation_id="get_inventory",
)
async def get_inventory_route(
    sku: str = Path(...),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> InventoryResponse:
    product = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
    if product is None:
        _ = create_event(
            db=db,
            event_type="inventory_lookup",
            lab_group=x_lab_group,
            resource_type="inventory",
            resource_id=sku,
            metadata={"found": False, "reason": "product_not_found"},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    inventory_rows = list(db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalars().all())
    if not inventory_rows:
        _ = create_event(
            db=db,
            event_type="inventory_lookup",
            lab_group=x_lab_group,
            resource_type="inventory",
            resource_id=sku,
            metadata={"found": False, "reason": "inventory_not_found"},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory not found")

    grouped_by_warehouse: dict[str, WarehouseStock] = {}
    for row in inventory_rows:
        if row.warehouse_id not in grouped_by_warehouse:
            grouped_by_warehouse[row.warehouse_id] = WarehouseStock(
                warehouse_id=row.warehouse_id,
                city=row.city,
                available=0,
                reserved=0,
            )
        grouped_by_warehouse[row.warehouse_id].available += row.available
        grouped_by_warehouse[row.warehouse_id].reserved += row.reserved

    warehouses = sorted(grouped_by_warehouse.values(), key=lambda item: item.warehouse_id)
    total_available = sum(warehouse.available for warehouse in warehouses)

    _ = create_event(
        db=db,
        event_type="inventory_lookup",
        lab_group=x_lab_group,
        resource_type="inventory",
        resource_id=sku,
        metadata={"warehouses": len(warehouses), "total_available": total_available},
    )

    return InventoryResponse(sku=sku, total_available=total_available, warehouses=warehouses)


@router.get(
    "/api/v1/inventory/{sku}/availability",
    response_model=AvailabilityResponse,
    tags=["Inventory"],
    operation_id="get_inventory_availability",
)
async def get_inventory_availability_route(
    sku: str = Path(...),
    postal_code: str = Query(...),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> AvailabilityResponse:
    product = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
    if product is None:
        _ = create_event(
            db=db,
            event_type="inventory_lookup",
            lab_group=x_lab_group,
            resource_type="inventory",
            resource_id=sku,
            metadata={"postal_code": postal_code, "found": False, "reason": "product_not_found"},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    warehouse_id, estimated_delivery_days = _get_delivery_mapping(postal_code)
    inventory_rows = list(db.execute(select(InventoryItem).where(InventoryItem.sku == sku)).scalars().all())
    quantity = sum(row.available for row in inventory_rows if row.warehouse_id == warehouse_id)

    _ = create_event(
        db=db,
        event_type="inventory_lookup",
        lab_group=x_lab_group,
        resource_type="inventory",
        resource_id=sku,
        metadata={
            "postal_code": postal_code,
            "warehouse_id": warehouse_id,
            "quantity": quantity,
            "estimated_delivery_days": estimated_delivery_days,
        },
    )

    return AvailabilityResponse(
        sku=sku,
        available=quantity > 0,
        quantity=quantity,
        estimated_delivery_days=estimated_delivery_days,
    )
