from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    order_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    carrier: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tracking_code: Mapped[str] = mapped_column(String, nullable=False)
    estimated_delivery: Mapped[date] = mapped_column(Date, nullable=False)
    last_update: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class ShipmentEvent(BaseModel):
    timestamp: datetime
    location: str
    status: str
    description: str


class ShipmentResponse(BaseModel):
    order_id: str
    shipment_id: str
    carrier: str
    status: str
    tracking_code: str
    estimated_delivery: date
    last_update: datetime
    events: list[ShipmentEvent] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)