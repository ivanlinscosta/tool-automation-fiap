from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    approval_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending_human_approval")
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lab_student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ApprovalRequestCreate(BaseModel):
    student_id: str
    request_type: str
    justification: str
    risk: Literal["low", "medium", "high"]


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    approved_by: str
    comment: str | None = None


class ApprovalRequestResponse(BaseModel):
    approval_id: str
    student_id: str
    request_type: str
    justification: str
    risk: str
    status: str
    requires_human_approval: bool
    approved_by: str | None = None
    decision: str | None = None
    decision_comment: str | None = None
    decision_at: datetime | None = None
    lab_student_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
