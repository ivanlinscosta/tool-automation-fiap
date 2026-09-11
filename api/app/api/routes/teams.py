from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path, status

from app.db.seed import TEAMS
from app.models.team import Team, TeamResponse


router = APIRouter()


def _team_value(team_data: Any, key: str) -> Any:
    if isinstance(team_data, Mapping):
        return team_data.get(key)
    return getattr(team_data, key, None)


def _coerce_team_response(team_data: Any, category: str) -> TeamResponse:
    if isinstance(team_data, Team):
        return TeamResponse(
            category=team_data.category,
            team=team_data.team,
            email=team_data.email,
            queue=team_data.queue,
            sla_default_hours=team_data.sla_default_hours,
        )

    if isinstance(team_data, Mapping):
        payload = dict(team_data)
        payload.setdefault("category", category)
    else:
        payload = team_data

    if hasattr(TeamResponse, "model_validate"):
        return TeamResponse.model_validate(payload)
    return TeamResponse(**payload)


def _find_team(category: str) -> TeamResponse | None:
    normalized_category = category.lower()

    if isinstance(TEAMS, Mapping):
        if normalized_category in TEAMS:
            return _coerce_team_response(TEAMS[normalized_category], normalized_category)

        for key, value in TEAMS.items():
            if str(key).lower() == normalized_category:
                return _coerce_team_response(value, normalized_category)
            if str(_team_value(value, "category") or "").lower() == normalized_category:
                return _coerce_team_response(value, normalized_category)

    for team_data in TEAMS:
        if str(_team_value(team_data, "category") or "").lower() == normalized_category:
            return _coerce_team_response(team_data, normalized_category)

    return None


@router.get(
    "/api/v1/teams/{category}",
    response_model=TeamResponse,
    tags=["Teams"],
    operation_id="get_team",
    summary="Get team by category",
    description="Retrieve team info for a given category. Valid categories: it, hr, finance, facilities, security, other",
    responses={
        200: {"description": "Team retrieved successfully"},
        404: {"description": "Team not found for the requested category"},
    },
)
async def get_team(
    category: str = Path(..., examples=["it"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> TeamResponse:
    _ = (x_student_id, x_request_id)
    team = _find_team(category)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team not found for category: {category}",
        )
    return team
