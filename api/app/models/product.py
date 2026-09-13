from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Product(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    subcategory: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="BRL")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rating: Mapped[float] = mapped_column(Float, nullable=False)


class ProductResponse(BaseModel):
    sku: str
    name: str
    category: str
    subcategory: str
    brand: str
    price: float
    currency: str
    active: bool
    rating: float

    model_config = ConfigDict(from_attributes=True)


class CatalogStatsResponse(BaseModel):
    total_skus: int
    active_skus: int
    categories: int
    countries: int