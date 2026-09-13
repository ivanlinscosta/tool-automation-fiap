from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Interaction(Base):
    __tablename__ = "interactions"

    interaction_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    lab_group: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InteractionCreate(BaseModel):
    customer_id: str
    channel: str
    message: str
    response: str
    source: str = Field(default="ai-agent")


class InteractionResponse(BaseModel):
    interaction_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InteractionDetail(BaseModel):
    interaction_id: str
    customer_id: str
    channel: str
    message: str
    response: str
    source: str
    lab_group: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)