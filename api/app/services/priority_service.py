from typing import Literal

from ..models.priority import PriorityRequest, PriorityResponse


ImpactLevel = Literal["low", "medium", "high"]
UrgencyLevel = Literal["low", "medium", "high"]
PriorityLevel = Literal["low", "medium", "high", "critical"]


PRIORITY_MATRIX: dict[tuple[ImpactLevel, UrgencyLevel], tuple[PriorityLevel, int]] = {
    ("low", "low"): ("low", 24),
    ("low", "medium"): ("low", 12),
    ("low", "high"): ("medium", 8),
    ("medium", "low"): ("low", 12),
    ("medium", "medium"): ("medium", 6),
    ("medium", "high"): ("high", 4),
    ("high", "low"): ("medium", 8),
    ("high", "medium"): ("high", 2),
    ("high", "high"): ("critical", 1),
}

CAMPUS_ACCESS_PRIORITY: dict[UrgencyLevel, tuple[PriorityLevel, int]] = {
    "low": ("high", 4),
    "medium": ("high", 2),
    "high": ("critical", 1),
}


def calculate_priority(priority_request: PriorityRequest) -> PriorityResponse:
    category = priority_request.category.strip().lower()

    if category == "campus_access":
        priority, sla_hours = CAMPUS_ACCESS_PRIORITY[priority_request.urgency]
        rule = f"campus_access_{priority_request.urgency}_campus_access_override"
    else:
        priority, sla_hours = PRIORITY_MATRIX[(priority_request.impact, priority_request.urgency)]
        rule = f"{priority_request.impact}_{priority_request.urgency}_impact_urgency"

    return PriorityResponse(
        priority=priority,
        sla_hours=sla_hours,
        requires_escalation=priority in {"high", "critical"},
        rule=rule,
    )
