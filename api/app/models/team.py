from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Team(Base):
    __tablename__: str = "teams"

    category: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    team_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    queue: Mapped[str] = mapped_column(String, nullable=False)
    sla_default_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    def __init__(self, **kwargs):
        team_alias = kwargs.pop("team", None)
        super().__init__(**kwargs)
        if team_alias is not None:
            self.team_name = team_alias

    @property
    def team(self) -> str:
        return self.team_name

    @team.setter
    def team(self, value: str) -> None:
        self.team_name = value


class TeamResponse(BaseModel):
    category: str = Field(description="Normalized support category key.")
    team: str = Field(description="Display name of the team responsible for the category.")
    email: str = Field(description="Shared team contact email address.")
    queue: str = Field(description="Internal support queue used for assignment.")
    sla_default_hours: int = Field(description="Default SLA in hours for the team queue.")

    model_config = ConfigDict(from_attributes=True)
