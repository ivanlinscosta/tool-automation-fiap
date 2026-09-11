from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class StudentRequest(Base):
    __tablename__ = "student_requests"

    request_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    protocol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assigned_department: Mapped[str] = mapped_column(String, nullable=False)
    queue: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    lab_student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudentRequestCreate(BaseModel):
    student_id: str
    category: str
    priority: str = Field(default="medium")
    summary: str
    description: str
    source: str = Field(default="api")


class StudentRequestResponse(BaseModel):
    request_id: str
    protocol: str
    status: str
    student_id: str
    category: str
    priority: str
    assigned_department: str
    queue: str
    summary: str
    description: str
    source: str
    lab_student_id: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class StudentRequestUpdate(BaseModel):
    status: Literal["open", "in_progress", "waiting_student", "waiting_human_approval", "resolved", "closed"] | None = None
    priority: str | None = None
    assigned_department: str | None = None


class StudentRequestFilter(BaseModel):
    student_id: str | None = None
    category: str | None = None
    priority: str | None = None
    status: str | None = None
