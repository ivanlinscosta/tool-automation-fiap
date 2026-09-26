import hmac
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db.database import get_db
from .registry import LAB_GROUPS, LABS_BASE_PATH, LabGroup, ensure_group_seeded
from .scenarios import SCENARIOS


logger = logging.getLogger(__name__)

LABS_GROUP_PATH = f"{LABS_BASE_PATH}/groups/{{group_id}}"

GroupId = Annotated[
    str,
    Path(
        description="Lab group identifier. Accepts 1-12, 01-12 or group-1..group-12.",
        examples=["01", "group-01"],
    ),
]

LabGroupHeader = Annotated[
    str,
    Header(alias="X-Lab-Group", description="Student or team identifier used for audit events."),
]

Scenario = Annotated[
    str | None,
    Query(
        description="Controlled failure injection: success, validation_error, not_found, duplicate, timeout, server_error.",
        examples=["success", "duplicate", "timeout"],
    ),
]

InstructorKey = Annotated[
    str | None,
    Header(alias="X-Instructor-Key", description="Required only for instructor-only endpoints exposing ground truth."),
]


def require_instructor_key(key: str | None) -> None:
    expected = settings.LABS_INSTRUCTOR_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor endpoints are disabled because LABS_INSTRUCTOR_KEY is not configured",
        )
    if not key or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-Instructor-Key")


def resolve_lab_group(group_id: str) -> LabGroup:
    key = group_id.strip().lower()
    normalized = key.split("-", maxsplit=1)[1] if key.startswith("group-") else key
    group = LAB_GROUPS.get(int(normalized)) if normalized.isdigit() else None
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lab group '{group_id}'. Valid values: 1-12, 01-12 or group-1..group-12.",
        )
    return group


def lab_group(group_id: str, db: Session) -> LabGroup:
    group = resolve_lab_group(group_id)
    try:
        ensure_group_seeded(db, group.group_id)
    except Exception:
        logger.exception("Failed to seed lab group %d", group.group_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Lab group {group.group_id:02d} seed is not available in this environment",
        ) from None
    return group


def require_group(expected_group_id: int) -> Callable[..., LabGroup]:
    def _dependency(
        group_id: GroupId,
        db: Session = Depends(get_db),
    ) -> LabGroup:
        group = resolve_lab_group(group_id)
        if group.group_id != expected_group_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Endpoint does not belong to lab group {expected_group_id:02d}",
            )
        return lab_group(group_id, db)

    return _dependency


def scenario_or_422(scenario: str | None) -> str | None:
    if scenario is None or scenario in SCENARIOS:
        return scenario
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unknown scenario '{scenario}'. Supported values: {', '.join(SCENARIOS)}",
    )


def entity_not_found(entity: str, identifier: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} '{identifier}' not found")


def lab_metadata(group: LabGroup) -> dict[str, object]:
    return {
        "group_id": f"{group.group_id:02d}",
        "slug": group.slug,
        "title": group.title,
        "summary": group.summary,
    }
