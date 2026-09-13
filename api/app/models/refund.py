from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Refund(Base):
    __tablename__ = "refunds"

    refund_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    order_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    approval_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="processing", index=True)
    lab_group: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RefundCreate(BaseModel):
    order_id: str
    amount: float
    reason: str
    approval_id: str | None = Field(default=None)


class RefundResponse(BaseModel):
    refund_id: str
    status: str
    amount: float

    model_config = ConfigDict(from_attributes=True)