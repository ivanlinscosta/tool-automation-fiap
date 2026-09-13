from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class ReturnRecord(Base):
    __tablename__ = "returns"

    return_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    protocol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="requested", index=True)
    lab_group: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ReturnCreate(BaseModel):
    customer_id: str
    order_id: str
    sku: str
    reason: str


class ReturnResponse(BaseModel):
    return_id: str
    status: str
    protocol: str

    model_config = ConfigDict(from_attributes=True)


class ReturnEligibilityRequest(BaseModel):
    order_id: str
    sku: str


class ReturnEligibilityResponse(BaseModel):
    eligible: bool
    reason: str
    days_since_delivery: int | None = None
    return_window_days: int
    policy_id: str | None = None