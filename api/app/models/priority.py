from typing import Literal

from pydantic import BaseModel, Field


class PriorityRequest(BaseModel):
    employee_id: str = Field(description="Employee identifier requesting support.")
    category: str = Field(description="Support category used for routing and overrides.")
    impact: Literal["low", "medium", "high"] = Field(description="Business impact level reported for the issue.")
    urgency: Literal["low", "medium", "high"] = Field(description="Urgency level reported for the issue.")


class PriorityResponse(BaseModel):
    priority: Literal["low", "medium", "high", "critical"] = Field(description="Calculated ticket priority.")
    sla_hours: int = Field(description="Expected SLA target in hours based on the calculation rule.")
    requires_escalation: bool = Field(description="Whether the request should be escalated immediately.")
    rule: str = Field(description="Rule identifier describing which priority policy was applied.")
