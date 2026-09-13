from pydantic import BaseModel, ConfigDict
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String, nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False, index=True)
    available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WarehouseStock(BaseModel):
    warehouse_id: str
    city: str
    available: int
    reserved: int


class InventoryResponse(BaseModel):
    sku: str
    total_available: int
    warehouses: list[WarehouseStock]

    model_config = ConfigDict(from_attributes=True)


class AvailabilityResponse(BaseModel):
    sku: str
    available: bool
    quantity: int
    estimated_delivery_days: int