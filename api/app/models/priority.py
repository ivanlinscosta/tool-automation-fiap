from typing import Literal

from pydantic import BaseModel, Field


class PriorityRequest(BaseModel):
    student_id: str = Field(description="Fictional student identifier requesting support.")
    category: str = Field(description="Academic support category used for routing and overrides.")
    impact: Literal["low", "medium", "high"] = Field(description="Reported impact level for the academic request.")
    urgency: Literal["low", "medium", "high"] = Field(description="Reported urgency level for the academic request.")


class PriorityResponse(BaseModel):
    priority: Literal["low", "medium", "high", "critical"] = Field(description="Calculated request priority.")
    sla_hours: int = Field(description="Expected SLA target in hours based on the calculation rule.")
    requires_escalation: bool = Field(description="Whether the request should be escalated immediately.")
    rule: str = Field(description="Rule identifier describing which priority policy was applied.")
