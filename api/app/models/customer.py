from datetime import date

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String, nullable=False, index=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    segment: Mapped[str] = mapped_column(String, nullable=False, index=True)
    loyalty_tier: Mapped[str] = mapped_column(String, nullable=False, index=True)
    customer_since: Mapped[date] = mapped_column(Date, nullable=False)
    lifetime_value: Mapped[float] = mapped_column(Float, nullable=False)
    preferred_channel: Mapped[str] = mapped_column(String, nullable=False)
    total_orders: Mapped[int] = mapped_column(nullable=False, default=0)


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    country: str
    city: str
    segment: str
    loyalty_tier: str
    customer_since: date
    lifetime_value: float
    preferred_channel: str

    model_config = ConfigDict(from_attributes=True)


class CustomerContextResponse(BaseModel):
    customer_id: str
    segment: str
    loyalty_tier: str
    total_orders: int
    open_orders: int
    open_support_cases: int
    returns_last_12_months: int
    lifetime_value: float


class RecommendationContextResponse(BaseModel):
    customer_id: str
    recent_categories: list[str]
    recent_products: list[str]
    preferred_brands: list[str]
    average_order_value: float
    price_sensitivity: str = Field(description="low, medium or high")