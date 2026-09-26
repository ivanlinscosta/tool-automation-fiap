import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.deps import LABS_BASE_PATH, require_instructor_key
from ....labs.generators import LAB_MIN_RECORDS, LAB_SEED, LAB_TODAY
from ....labs.registry import (
    LAB_GROUPS,
    LabGroup,
    ensure_group_seeded,
    group_model_map,
    is_group_seeded,
    load_lab_models,
    purge_group,
)
from ....labs.scenarios import SCENARIOS, SCENARIO_DESCRIPTIONS, scenario_docs
from ....config import settings
from ....services.audit_service import create_event


logger = logging.getLogger(__name__)

router = APIRouter()
TAG = "Lab - Plataforma"

InstructorKey = Annotated[
    str | None,
    Header(alias="X-Instructor-Key", description="Required to reset lab groups or read referential integrity."),
]


class LabGroupSummary(BaseModel):
    group_id: str = Field(description="Two-digit group identifier, e.g. 01.")
    slug: str
    title: str
    summary: str
    tag: str
    models: list[str]
    record_counts: dict[str, int]
    total_records: int
    meets_minimum: bool
    seeded: bool


class LabGroupsResponse(BaseModel):
    total_groups: int
    min_records_per_group: int
    seed: int
    reference_date: str
    groups: list[LabGroupSummary]


class RelationViolation(BaseModel):
    group_id: str
    child_model: str
    child_field: str
    parent_model: str
    parent_field: str
    orphan_count: int
    samples: list[str]


class IntegrityReport(BaseModel):
    group_id: str
    seeded: bool
    checked_relations: int
    violations: list[RelationViolation]
    healthy: bool


class ResetRequest(BaseModel):
    groups: list[int] | None = Field(
        default=None,
        description="Group numbers to reset. Omit or send null to reset every group.",
        examples=[[1, 2]],
    )

    model_config = ConfigDict(json_schema_extra={"examples": [{"groups": [1]}, {"groups": None}]})


class ResetResult(BaseModel):
    reset_groups: list[str]
    skipped_groups: dict[str, str] = Field(default_factory=dict)
    record_counts: dict[str, int]
    elapsed_ms: int


def _is_seeded(db: Session, group: LabGroup) -> bool:
    try:
        return is_group_seeded(db, group)
    except Exception:
        logger.warning("Lab group %d is not available in this environment", group.group_id)
        return False


def _record_counts(db: Session, group: LabGroup) -> dict[str, int]:
    return {
        name: int(db.execute(select(func.count()).select_from(model)).scalar_one())
        for name, model in group_model_map(group).items()
    }


@router.get(
    f"{LABS_BASE_PATH}/groups",
    response_model=LabGroupsResponse,
    tags=[TAG],
    operation_id="labs_list_groups",
    summary="List all lab groups with their record counts",
)
async def list_lab_groups(db: Session = Depends(get_db)) -> LabGroupsResponse:
    summaries: list[LabGroupSummary] = []
    for group_id in sorted(LAB_GROUPS):
        group = LAB_GROUPS[group_id]
        seeded = _is_seeded(db, group)
        counts = _record_counts(db, group) if seeded else {name: 0 for name in group.models}
        summaries.append(
            LabGroupSummary(
                group_id=f"{group_id:02d}",
                slug=group.slug,
                title=group.title,
                summary=group.summary,
                tag=group.tag,
                models=list(group.models),
                record_counts=counts,
                total_records=sum(counts.values()),
                meets_minimum=counts.get(group.probe, 0) >= LAB_MIN_RECORDS,
                seeded=seeded,
            )
        )
    return LabGroupsResponse(
        total_groups=len(LAB_GROUPS),
        min_records_per_group=LAB_MIN_RECORDS,
        seed=LAB_SEED,
        reference_date=LAB_TODAY.isoformat(),
        groups=summaries,
    )


@router.get(
    f"{LABS_BASE_PATH}/meta",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_meta",
    summary="Lab platform metadata, supported scenarios and conventions",
)
async def labs_meta(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "base_path": LABS_BASE_PATH,
        "group_count": len(LAB_GROUPS),
        "available_groups": [f"{group_id:02d}" for group_id in sorted(LAB_GROUPS)],
        "seeded_groups": [f"{group.group_id:02d}" for group in LAB_GROUPS.values() if _is_seeded(db, group)],
        "seed": LAB_SEED,
        "reference_date": LAB_TODAY.isoformat(),
        "min_records_per_group": LAB_MIN_RECORDS,
        "scenarios": {
            "supported": list(SCENARIOS),
            "descriptions": SCENARIO_DESCRIPTIONS,
            "enabled": settings.LABS_ALLOW_SCENARIOS,
        },
        "conventions": {
            "group_id_aliases": ["1", "01", "group-1", "group-01"],
            "pagination": {"envelope": ["items", "meta"], "max_limit": 200},
            "sorting": {"params": ["sort", "order"], "invalid_field_status": 400},
            "errors": {"unknown_entity": 404, "unknown_sort": 400, "invalid_payload": 422, "conflict": 409},
            "instructor_namespace": f"{LABS_BASE_PATH}/groups/{{group_id}}/instructor",
            "instructor_header": "X-Instructor-Key",
            "data_policy": "Student endpoints never expose ground truth labels; use the instructor namespace.",
        },
        "scenario_docs": scenario_docs(),
    }


@router.get(
    f"{LABS_BASE_PATH}/groups/{{group_id}}/integrity",
    response_model=IntegrityReport,
    tags=[TAG],
    operation_id="labs_check_integrity",
    summary="Instructor only: check referential integrity of a lab group",
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled on this environment"},
    },
)
async def check_integrity(
    group_id: str,
    instructor_key: InstructorKey = None,
    sample_size: int = Query(default=5, ge=1, le=50, description="Orphan identifiers returned per violation."),
    db: Session = Depends(get_db),
) -> IntegrityReport:
    require_instructor_key(instructor_key)
    from ....labs.deps import resolve_lab_group

    group = resolve_lab_group(group_id)
    try:
        ensure_group_seeded(db, group.group_id)
    except Exception:
        return IntegrityReport(
            group_id=f"{group.group_id:02d}",
            seeded=False,
            checked_relations=0,
            violations=[],
            healthy=True,
        )

    models = group_model_map(group)
    violations: list[RelationViolation] = []
    for child_name, child_field, parent_ref in group.relations:
        parent_model_name, _, parent_field = parent_ref.partition(".")
        child_model = models[child_name]
        parent_model = models[parent_model_name]
        child_column = getattr(child_model, child_field)
        parent_column = getattr(parent_model, parent_field)

        parent_values = {value for value in db.execute(select(parent_column).distinct()).scalars().all() if value is not None}
        child_values = [value for value in db.execute(select(child_column)).scalars().all() if value is not None]
        orphans = sorted({value for value in child_values if value not in parent_values})
        if orphans:
            violations.append(
                RelationViolation(
                    group_id=f"{group.group_id:02d}",
                    child_model=child_name,
                    child_field=child_field,
                    parent_model=parent_model_name,
                    parent_field=parent_field,
                    orphan_count=len(orphans),
                    samples=[str(value) for value in orphans[:sample_size]],
                )
            )

    return IntegrityReport(
        group_id=f"{group.group_id:02d}",
        seeded=True,
        checked_relations=len(group.relations),
        violations=violations,
        healthy=not violations,
    )


@router.post(
    f"{LABS_BASE_PATH}/reset",
    response_model=ResetResult,
    tags=[TAG],
    operation_id="labs_reset",
    summary="Instructor only: purge and re-seed lab groups deterministically",
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled on this environment"},
        404: {"description": "Unknown lab group"},
    },
)
async def reset_labs(
    payload: ResetRequest | None = None,
    instructor_key: InstructorKey = None,
    db: Session = Depends(get_db),
) -> ResetResult:
    import time

    require_instructor_key(instructor_key)
    started = time.perf_counter()
    requested = payload.groups if payload and payload.groups is not None else sorted(LAB_GROUPS)

    unknown = [group_id for group_id in requested if group_id not in LAB_GROUPS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lab group(s): {', '.join(str(item) for item in unknown)}",
        )

    counts: dict[str, int] = {}
    skipped: dict[str, str] = {}

    for group_id in requested:
        try:
            purge_group(db, group_id)
            ensure_group_seeded(db, group_id)
        except Exception as exc:
            db.rollback()
            skipped[f"{group_id:02d}"] = f"{type(exc).__name__}: {exc}"
            logger.warning("Skipped lab group %d during reset: %s", group_id, exc)
            continue
        counts[f"{group_id:02d}"] = sum(_record_counts(db, LAB_GROUPS[group_id]).values())

    elapsed = int((time.perf_counter() - started) * 1000)
    create_event(
        db,
        event_type="lab_groups_reset",
        lab_group="instructor",
        resource_type="lab_platform",
        resource_id="reset",
        metadata={
            "groups": [f"{group_id:02d}" for group_id in requested if f"{group_id:02d}" not in skipped],
            "skipped": sorted(skipped),
            "elapsed_ms": elapsed,
        },
    )
    return ResetResult(
        reset_groups=sorted(counts),
        skipped_groups=skipped,
        record_counts=counts,
        elapsed_ms=elapsed,
    )


@router.get(
    f"{LABS_BASE_PATH}/groups/{{group_id}}/models",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group_models",
    summary="Inspect the tables registered for a lab group",
)
async def group_models(group_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ....labs.deps import resolve_lab_group

    group = resolve_lab_group(group_id)
    tables = {model.__tablename__: model.__table__.columns.keys() for model in load_lab_models(group)}
    return {
        "group_id": f"{group.group_id:02d}",
        "slug": group.slug,
        "seeded": is_group_seeded(db, group),
        "tables": tables,
        "relations": [
            {"child": child, "field": field, "parent": parent} for child, field, parent in group.relations
        ],
    }
