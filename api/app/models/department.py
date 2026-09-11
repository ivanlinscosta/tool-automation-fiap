from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Department(Base):
    __tablename__ = "departments"

    category: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    department_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    queue: Mapped[str] = mapped_column(String, nullable=False)
    sla_default_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_human_for_sensitive_actions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DepartmentResponse(BaseModel):
    category: str
    department: str = Field(alias="department_name")
    email: str
    queue: str
    sla_default_hours: int
    requires_human_for_sensitive_actions: bool

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
