from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base


class Event(Base):
    __tablename__: str = "events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    lab_group: Mapped[str] = mapped_column(String, nullable=False, index=True)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)


class EventResponse(BaseModel):
    event_id: str = Field(description="Unique event identifier.")
    event_type: str = Field(description="Event classification or verb describing the action.")
    lab_group: str = Field(description="Lab group identifier captured from the X-Lab-Group header.")
    customer_id: str | None = Field(default=None, description="Customer identifier related to the event, when applicable.")
    timestamp: datetime = Field(description="UTC timestamp when the event was recorded.")
    resource_type: str = Field(description="Domain resource type related to the event.")
    resource_id: str = Field(description="Domain resource identifier related to the event.")
    metadata_json: str = Field(description="Serialized JSON metadata payload for audit details.")

    model_config = ConfigDict(from_attributes=True)