from pydantic import BaseModel, ConfigDict
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    course: Mapped[str] = mapped_column(String, nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    shift: Mapped[str] = mapped_column(String, nullable=False)
    campus: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")


class StudentResponse(BaseModel):
    id: str
    name: str
    course: str
    semester: int
    shift: str
    campus: str
    email: str
    status: str

    model_config = ConfigDict(from_attributes=True)
