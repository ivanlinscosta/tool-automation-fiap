from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Approval(Base):
    __tablename__ = "approvals"

    approval_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reference_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String, nullable=False, default="ai-agent")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    lab_group: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalCreate(BaseModel):
    type: str
    reference_id: str
    requested_by: str = Field(default="ai-agent")
    amount: float = Field(default=0)
    reason: str


class ApprovalDecision(BaseModel):
    decision: str = Field(description="approved or rejected")
    comment: str = Field(default="")


class ApprovalResponse(BaseModel):
    approval_id: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ApprovalDetail(BaseModel):
    approval_id: str
    type: str
    reference_id: str
    requested_by: str
    amount: float
    reason: str
    status: str
    decision: str | None = None
    comment: str | None = None
    decided_by: str | None = None
    lab_group: str
    created_at: datetime
    decided_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)