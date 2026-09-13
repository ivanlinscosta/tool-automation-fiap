from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.shipment import Shipment, ShipmentResponse
from ...services.audit_service import create_event


router = APIRouter()


@router.get(
    "/api/v1/shipments/{shipment_id}",
    response_model=ShipmentResponse,
    tags=["Logistics"],
    operation_id="get_shipment_by_id",
    responses={404: {"description": "Shipment not found"}},
)
async def get_shipment_by_id(
    shipment_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    shipment = db.execute(select(Shipment).where(Shipment.shipment_id == shipment_id)).scalar_one_or_none()
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    _ = create_event(
        db,
        "shipment_lookup",
        x_lab_group,
        "shipment",
        shipment.shipment_id,
        metadata={"order_id": shipment.order_id},
    )
    return ShipmentResponse.model_validate(shipment)
