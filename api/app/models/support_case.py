from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class SupportCase(Base):
    __tablename__ = "support_cases"

    case_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    protocol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open", index=True)
    priority: Mapped[str] = mapped_column(String, nullable=False, default="P3", index=True)
    lab_group: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SupportCaseCreate(BaseModel):
    customer_id: str
    category: str
    summary: str
    description: str


class SupportCaseResponse(BaseModel):
    case_id: str
    status: str
    protocol: str

    model_config = ConfigDict(from_attributes=True)


class SupportCaseDetail(BaseModel):
    case_id: str
    protocol: str
    customer_id: str
    category: str
    summary: str
    description: str
    status: str
    priority: str
    lab_group: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PriorityCheckRequest(BaseModel):
    category: str
    impact: str
    urgency: str


class PriorityCheckResponse(BaseModel):
    priority: str
    sla_hours: int