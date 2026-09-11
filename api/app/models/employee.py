from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Employee(Base):
    __tablename__: str = "employees"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    vip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EmployeeResponse(BaseModel):
    id: str = Field(description="Unique employee identifier, such as EMP001.")
    name: str = Field(description="Fictional employee full name.")
    department: str = Field(description="Employee department.")
    email: str = Field(description="Employee corporate email address.")
    role: str = Field(description="Employee role or job title.")
    vip: bool = Field(description="Whether the employee is treated as VIP in the lab.")

    model_config = ConfigDict(from_attributes=True)
