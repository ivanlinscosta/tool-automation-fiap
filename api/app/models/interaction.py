from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Interaction(Base):
    __tablename__ = "interactions"

    interaction_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    response_type: Mapped[str] = mapped_column(String, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_articles: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    lab_student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InteractionCreate(BaseModel):
    student_id: str
    request_text: str
    category: str
    response_type: str = Field(description="automatic or human")
    response_text: str
    knowledge_articles: list[str] = Field(default_factory=list)
    source: str = Field(default="api")


class InteractionResponse(BaseModel):
    interaction_id: str
    student_id: str
    request_text: str
    category: str
    response_type: str
    response_text: str
    knowledge_articles: list[str]
    source: str
    lab_student_id: str
    created_at: datetime
