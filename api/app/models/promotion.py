from datetime import date

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Promotion(Base):
    __tablename__ = "promotions"

    promotion_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    starts_at: Mapped[date] = mapped_column(Date, nullable=False)
    ends_at: Mapped[date] = mapped_column(Date, nullable=False)


class PromotionResponse(BaseModel):
    promotion_id: str
    name: str
    description: str
    discount_pct: float
    category: str | None
    brand: str | None
    country: str | None
    min_price: float | None
    active: bool
    starts_at: date
    ends_at: date

    model_config = ConfigDict(from_attributes=True)


class PromotionEligibleItem(BaseModel):
    promotion_id: str
    name: str
    discount_pct: float
    eligible: bool