from datetime import date

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False, index=True)
    content: Mapped[str] = mapped_column(nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)


class PolicyResponse(BaseModel):
    id: str
    category: str
    title: str
    country: str
    content: str
    effective_from: date

    model_config = ConfigDict(from_attributes=True)