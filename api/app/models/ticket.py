from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Ticket(Base):
    __tablename__: str = "tickets"

    ticket_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    employee_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assigned_team: Mapped[str] = mapped_column(String, nullable=False)
    queue: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TicketCreate(BaseModel):
    employee_id: str = Field(description="Employee identifier opening the ticket.")
    category: str = Field(description="Requested support category used for routing.")
    impact: Literal["low", "medium", "high"] = Field(description="Reported business impact used in deterministic prioritization.")
    urgency: Literal["low", "medium", "high"] = Field(description="Reported urgency used in deterministic prioritization.")
    summary: str = Field(description="Short summary of the ticket issue.")
    description: str = Field(description="Detailed description of the support request.")
    source: str = Field(default="api", description="Origin channel of the ticket, such as api, portal, or email.")


class TicketResponse(BaseModel):
    ticket_id: str = Field(description="Unique ticket identifier in the format TK-XXXX.")
    status: str = Field(description="Current lifecycle status of the ticket.")
    employee_id: str = Field(description="Employee identifier associated with the ticket.")
    category: str = Field(description="Normalized routing category.")
    priority: str = Field(description="Calculated priority value.")
    assigned_team: str = Field(description="Team assigned to handle the ticket.")
    queue: str = Field(description="Queue used for operational processing.")
    summary: str = Field(description="Short summary of the ticket issue.")
    description: str = Field(description="Detailed description of the ticket issue.")
    source: str = Field(description="Origin channel of the ticket.")
    student_id: str = Field(description="Student identifier captured from the request context.")
    created_at: datetime = Field(description="UTC timestamp when the ticket was created.")
    updated_at: datetime | None = Field(default=None, description="UTC timestamp of the latest ticket update, when available.")

    model_config = ConfigDict(from_attributes=True)


class TicketFilter(BaseModel):
    employee_id: str | None = Field(default=None, description="Optional employee identifier filter.")
    category: str | None = Field(default=None, description="Optional category filter.")
    priority: str | None = Field(default=None, description="Optional priority filter.")
    status: str | None = Field(default=None, description="Optional ticket status filter.")
