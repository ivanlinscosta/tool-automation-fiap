from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AccessRequest(Base):
    __tablename__: str = "access_requests"

    request_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    employee_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AccessRequestCreate(BaseModel):
    employee_id: str = Field(description="Employee identifier requesting access.")
    resource: str = Field(description="Target system, dataset, or resource requested.")
    justification: str = Field(description="Business justification for requesting access.")
    risk: Literal["low", "medium", "high"] = Field(description="Risk assessment used to determine the approval path.")


class AccessRequestApproval(BaseModel):
    approved_by: str = Field(description="Actor or approver responsible for the decision.")
    decision: Literal["approved", "rejected"] = Field(description="Final human decision for a pending access request.")
    decision_comment: str | None = Field(default=None, description="Optional reviewer comment explaining the approval or rejection.")


class AccessRequestResponse(BaseModel):
    request_id: str = Field(description="Unique access request identifier in the format AR-XXX.")
    employee_id: str = Field(description="Employee identifier associated with the request.")
    resource: str = Field(description="Requested system or resource.")
    justification: str = Field(description="Business justification provided by the employee.")
    risk: str = Field(description="Risk level assigned to the request.")
    status: str = Field(description="Current request status, including didactic auto-approval when applicable.")
    requires_human_approval: bool = Field(description="Whether a human approver is required for this request.")
    approved_by: str | None = Field(default=None, description="Actor who approved or rejected the request, when available.")
    decision: str | None = Field(default=None, description="Recorded decision outcome for the request.")
    decision_comment: str | None = Field(default=None, description="Optional decision notes or reviewer comment.")
    decision_at: datetime | None = Field(default=None, description="UTC timestamp when the request was decided, when available.")
    student_id: str = Field(description="Student identifier captured from the request context.")
    created_at: datetime = Field(description="UTC timestamp when the access request was created.")

    model_config = ConfigDict(from_attributes=True)
