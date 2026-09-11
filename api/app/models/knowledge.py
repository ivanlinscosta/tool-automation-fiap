from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    can_answer_automatically: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False, default="didactic")


class KnowledgeArticleResponse(BaseModel):
    id: str
    title: str
    category: str
    keywords: list[str]
    content: str
    can_answer_automatically: bool
    requires_human: bool
    last_updated: datetime
    source_type: str


class KnowledgeSearchResult(BaseModel):
    id: str
    title: str
    category: str
    score: float
    content: str


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[KnowledgeSearchResult]
