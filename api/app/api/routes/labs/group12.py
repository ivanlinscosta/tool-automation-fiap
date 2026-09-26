from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.artifacts import (
    build_metrics_json,
    build_model_binary,
    build_model_card_md,
    build_schema_yaml,
    sha256_hex,
)
from ....labs.deps import (
    LABS_GROUP_PATH,
    LabGroupHeader,
    Scenario,
    entity_not_found,
    require_group,
    scenario_or_422,
)
from ....labs.generators import LAB_NOW
from ....labs.pagination import apply_sort, build_page, page_params
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group12_models import (
    Deployment,
    DeploymentResponse,
    FeatureSchema,
    FeatureSchemaResponse,
    JiraTicket,
    JiraTicketResponse,
    Metrics,
    MetricsResponse,
    ModelArtifact,
    ModelArtifactResponse,
    ModelCard,
    ModelCardResponse,
    ModelNotification,
    ModelNotificationResponse,
    ModelSubmission,
    ModelSubmissionCreate,
    ModelSubmissionResponse,
    ValidationResult,
    ValidationResultResponse,
    ValidationSummaryResponse,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 12"
Group12 = Depends(require_group(12))


def _next_id(db: Session, model: type, field_name: str, prefix: str) -> str:
    field = getattr(model, field_name)
    highest = db.execute(
        select(field).order_by(field.desc()).limit(1)
    ).scalar_one_or_none()
    if highest is None:
        return f"{prefix}-000001"
    return f"{prefix}-{int(str(highest).rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _submission_or_404(db: Session, submission_id: str) -> ModelSubmission:
    row = db.get(ModelSubmission, submission_id)
    if row is None:
        raise entity_not_found("ModelSubmission", submission_id)
    return row


def _artifact_or_404(db: Session, artifact_id: str) -> ModelArtifact:
    row = db.get(ModelArtifact, artifact_id)
    if row is None:
        raise entity_not_found("ModelArtifact", artifact_id)
    return row


def _deployment_or_404(db: Session, deployment_id: str) -> Deployment:
    row = db.get(Deployment, deployment_id)
    if row is None:
        raise entity_not_found("Deployment", deployment_id)
    return row


def _validation_inputs(
    db: Session, submission: ModelSubmission
) -> tuple[ModelArtifact, list[Metrics], list[FeatureSchema], ModelCard]:
    artifact = db.execute(
        select(ModelArtifact)
        .where(ModelArtifact.submission_id == submission.submission_id)
        .order_by(ModelArtifact.id.asc())
        .limit(1)
    ).scalar_one()
    metrics_rows = list(
        db.execute(
            select(Metrics)
            .where(Metrics.submission_id == submission.submission_id)
            .order_by(Metrics.metric_name.asc())
        )
        .scalars()
        .all()
    )
    schema_rows = list(
        db.execute(
            select(FeatureSchema)
            .where(FeatureSchema.submission_id == submission.submission_id)
            .order_by(FeatureSchema.feature_name.asc())
        )
        .scalars()
        .all()
    )
    card = db.execute(
        select(ModelCard).where(ModelCard.model_id == submission.modelo_id).limit(1)
    ).scalar_one()
    return artifact, metrics_rows, schema_rows, card


def _build_validation_results(
    submission: ModelSubmission,
    artifact: ModelArtifact,
    metrics_rows: list[Metrics],
    schema_rows: list[FeatureSchema],
    card: ModelCard,
) -> list[tuple[str, str, str]]:
    payload = build_model_binary(
        artifact.id, submission.modelo_id, submission.version, artifact.size_bytes
    )
    results: list[tuple[str, str, str]] = []
    results.append(
        (
            "CHECKSUM",
            "PASS" if sha256_hex(payload) == artifact.sha256 else "FAIL",
            "Checksum confere com o binario recomputado."
            if sha256_hex(payload) == artifact.sha256
            else "SHA256 divergente do artefato recomputado.",
        )
    )
    schema_ok = all(
        row.dtype in {"int", "float", "string", "bool"} and not row.nullable
        for row in schema_rows
    )
    results.append(
        (
            "SCHEMA",
            "PASS" if schema_ok else "FAIL",
            "Schema aderente ao contrato."
            if schema_ok
            else "Schema contem dtype invalido ou feature nullable.",
        )
    )
    results.append(
        (
            "MODEL_CARD",
            "PASS" if card.completeness >= 60 else "FAIL",
            "Model card com completude suficiente."
            if card.completeness >= 60
            else "Model card abaixo de 60.",
        )
    )
    metrics_ok = all(
        row.metric_value >= row.threshold
        for row in metrics_rows
        if row.metric_name in {"auc", "f1", "precision", "recall"}
    )
    results.append(
        (
            "METRICS",
            "PASS" if metrics_ok else "FAIL",
            "Metricas acima dos thresholds."
            if metrics_ok
            else "Metricas abaixo do threshold minimo.",
        )
    )
    compliance_ok = submission.data_classificacao != "RESTRITO" or bool(
        card.approved_by
    )
    results.append(
        (
            "COMPLIANCE",
            "PASS" if compliance_ok else "FAIL",
            "Compliance aprovado."
            if compliance_ok
            else "Modelo RESTRITO sem aprovacao de compliance.",
        )
    )
    psi_row = next(row for row in metrics_rows if row.metric_name == "psi")
    bias_status = (
        "PASS"
        if psi_row.metric_value <= 0.2
        else "WARNING"
        if psi_row.metric_value <= 0.25
        else "FAIL"
    )
    results.append(
        (
            "BIAS",
            bias_status,
            "PSI dentro do esperado."
            if bias_status == "PASS"
            else "PSI em zona de atencao."
            if bias_status == "WARNING"
            else "PSI acima do limite.",
        )
    )
    return results


def _overall_status(rows: list[ValidationResult | tuple[str, str, str]]) -> str:
    statuses = [
        row.status if isinstance(row, ValidationResult) else row[1] for row in rows
    ]
    if "FAIL" in statuses:
        return "FAIL"
    if "WARNING" in statuses:
        return "WARNING"
    return "PASS"


@router.get(
    f"{PREFIX}/submissions",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_submissions",
    summary="List ML handover submissions",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_submissions(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    status_filter: str | None = Query(default=None, alias="status"),
    owner: str | None = Query(default=None),
    framework: str | None = Query(default=None),
    target_env: str | None = Query(default=None),
    data_classificacao: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default="submission_id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(ModelSubmission)
    if status_filter:
        query = query.where(ModelSubmission.status == status_filter)
    if owner:
        query = query.where(ModelSubmission.owner == owner)
    if framework:
        query = query.where(ModelSubmission.framework == framework)
    if target_env:
        query = query.where(ModelSubmission.target_env == target_env)
    if data_classificacao:
        query = query.where(ModelSubmission.data_classificacao == data_classificacao)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(ModelSubmission.modelo_id).like(pattern),
                func.lower(ModelSubmission.nome_modelo).like(pattern),
                func.lower(ModelSubmission.owner).like(pattern),
            )
        )
    query = apply_sort(query, ModelSubmission, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: ModelSubmissionResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/submissions/{{submission_id}}",
    response_model=ModelSubmissionResponse,
    tags=[TAG],
    operation_id="labs_group12_get_submission",
    summary="Get one submission",
    responses={
        404: {"description": "Submission not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def get_submission(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ModelSubmissionResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return ModelSubmissionResponse.model_validate(_submission_or_404(db, submission_id))


@router.get(
    f"{PREFIX}/artifacts",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_artifacts",
    summary="List model artifacts",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_artifacts(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    submission_id: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(ModelArtifact)
    if submission_id:
        query = query.where(ModelArtifact.submission_id == submission_id)
    query = apply_sort(query, ModelArtifact, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: ModelArtifactResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/metrics",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_metrics",
    summary="List metric rows",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_metrics_rows(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    submission_id: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Metrics)
    if submission_id:
        query = query.where(Metrics.submission_id == submission_id)
    query = apply_sort(query, Metrics, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: MetricsResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/feature-schema",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_feature_schema",
    summary="List feature schema rows",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_feature_schema_rows(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    submission_id: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(FeatureSchema)
    if submission_id:
        query = query.where(FeatureSchema.submission_id == submission_id)
    query = apply_sort(query, FeatureSchema, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: FeatureSchemaResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/model-cards",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_model_cards",
    summary="List model cards",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_model_cards(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    model_id: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(ModelCard)
    if model_id:
        query = query.where(ModelCard.model_id == model_id)
    query = apply_sort(query, ModelCard, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: ModelCardResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/validation-results",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_validation_results",
    summary="List validation results",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_validation_results(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    submission_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(ValidationResult)
    if submission_id:
        query = query.where(ValidationResult.submission_id == submission_id)
    if status_filter:
        query = query.where(ValidationResult.status == status_filter)
    query = apply_sort(query, ValidationResult, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: ValidationResultResponse.model_validate(
            row
        ).model_dump(),
    )


@router.get(
    f"{PREFIX}/deployments",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_deployments",
    summary="List deployments",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_deployments(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    model_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Deployment)
    if model_id:
        query = query.where(Deployment.model_id == model_id)
    if status_filter:
        query = query.where(Deployment.status == status_filter)
    query = apply_sort(query, Deployment, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: DeploymentResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/jira-tickets",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_jira_tickets",
    summary="List Jira tickets",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_jira_tickets(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    submission_id: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(JiraTicket)
    if submission_id:
        query = query.where(JiraTicket.submission_id == submission_id)
    query = apply_sort(query, JiraTicket, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: JiraTicketResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/model-notifications",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_list_notifications",
    summary="List model notifications",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_notifications(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    submission_id: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(ModelNotification)
    if submission_id:
        query = query.where(ModelNotification.submission_id == submission_id)
    query = apply_sort(query, ModelNotification, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: ModelNotificationResponse.model_validate(
            row
        ).model_dump(),
    )


@router.post(
    f"{PREFIX}/submissions",
    response_model=ModelSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group12_create_submission",
    summary="Create a submission with deterministic artifacts",
    responses={
        409: {"description": "Duplicate modelo_id"},
        422: {"description": "Validation error"},
    },
)
async def create_submission(
    payload: ModelSubmissionCreate,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ModelSubmissionResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if (
        db.execute(
            select(ModelSubmission).where(
                ModelSubmission.modelo_id == payload.modelo_id
            )
        ).scalar_one_or_none()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="modelo_id already exists"
        )
    submission = ModelSubmission(
        submission_id=_next_id(db, ModelSubmission, "submission_id", "SUB"),
        modelo_id=payload.modelo_id,
        nome_modelo=payload.nome_modelo,
        version=payload.version,
        owner=payload.owner,
        framework=payload.framework,
        submitted_at=LAB_NOW,
        status="SUBMETIDO",
        target_env=payload.target_env,
        data_classificacao=payload.data_classificacao,
    )
    db.add(submission)
    db.flush()
    artifact_id = _next_id(db, ModelArtifact, "id", "ART")
    binary = build_model_binary(
        artifact_id, payload.modelo_id, payload.version, payload.artifact_size_bytes
    )
    artifact = ModelArtifact(
        id=artifact_id,
        submission_id=submission.submission_id,
        filename=f"{payload.modelo_id}-{payload.version}.bin",
        content_type="application/octet-stream",
        size_bytes=payload.artifact_size_bytes,
        sha256=sha256_hex(binary),
        storage_path=f"/artifacts/{artifact_id}.bin",
        uploaded_at=LAB_NOW,
    )
    db.add(artifact)
    for metric_name, value in payload.metrics.items():
        threshold = (
            0.20 if metric_name == "psi" else 0.65 if metric_name != "auc" else 0.70
        )
        db.add(
            Metrics(
                id=f"MET-{submission.submission_id}-{metric_name}",
                submission_id=submission.submission_id,
                metric_name=metric_name,
                metric_value=float(value),
                dataset="validation",
                evaluated_at=LAB_NOW,
                threshold=threshold,
            )
        )
    for feature in payload.feature_schema:
        feature_name = str(feature["feature_name"]).replace(" ", "_")
        db.add(
            FeatureSchema(
                id=f"SCH-{submission.submission_id}-{feature_name}",
                submission_id=submission.submission_id,
                feature_name=str(feature["feature_name"]),
                dtype=str(feature["dtype"]),
                nullable=bool(feature["nullable"]),
                min_value=float(feature["min_value"])
                if feature.get("min_value") is not None
                else None,
                max_value=float(feature["max_value"])
                if feature.get("max_value") is not None
                else None,
                examples=str(feature.get("examples"))
                if feature.get("examples") is not None
                else None,
            )
        )
    db.add(
        ModelCard(
            id=f"CRD-{submission.submission_id}",
            model_id=submission.modelo_id,
            summary=str(payload.model_card.get("summary") or ""),
            intended_use=str(payload.model_card.get("intended_use") or ""),
            limitations=str(payload.model_card.get("limitations") or ""),
            ethical_considerations=str(
                payload.model_card.get("ethical_considerations") or ""
            ),
            license=str(payload.model_card.get("license") or "interna"),
            approved_by=str(payload.model_card.get("approved_by"))
            if payload.model_card.get("approved_by")
            else None,
            approved_at=LAB_NOW if payload.model_card.get("approved_by") else None,
            completeness=int(payload.model_card.get("completeness") or 0),
        )
    )
    db.commit()
    create_event(
        db,
        "lab_group12_submission_created",
        x_lab_group,
        "model_submission",
        submission.submission_id,
        {"group": "12", "modelo_id": submission.modelo_id},
    )
    return ModelSubmissionResponse.model_validate(submission)


@router.post(
    f"{PREFIX}/submissions/{{submission_id}}/validate",
    response_model=ValidationSummaryResponse,
    tags=[TAG],
    operation_id="labs_group12_validate_submission",
    summary="Run all deterministic validation checks",
    responses={
        404: {"description": "Submission not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def validate_submission(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ValidationSummaryResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    submission = _submission_or_404(db, submission_id)
    artifact, metrics_rows, schema_rows, card = _validation_inputs(db, submission)
    db.execute(
        delete(ValidationResult).where(ValidationResult.submission_id == submission_id)
    )
    checks = _build_validation_results(
        submission, artifact, metrics_rows, schema_rows, card
    )
    rows: list[ValidationResult] = []
    for check_name, check_status, detail in checks:
        row = ValidationResult(
            id=f"VAL-{submission_id}-{check_name}",
            submission_id=submission_id,
            check_name=check_name,
            status=check_status,
            detail=detail,
            checked_at=LAB_NOW,
        )
        db.add(row)
        rows.append(row)
    submission.status = (
        "REPROVADO" if _overall_status(checks) == "FAIL" else "EM_VALIDACAO"
    )
    db.commit()
    create_event(
        db,
        "lab_group12_submission_validated",
        x_lab_group,
        "model_submission",
        submission_id,
        {"group": "12"},
    )
    return ValidationSummaryResponse(
        submission_id=submission_id,
        overall_status=_overall_status(rows),
        checks=[ValidationResultResponse.model_validate(row) for row in rows],
    )


@router.get(
    f"{PREFIX}/submissions/{{submission_id}}/validation-summary",
    response_model=ValidationSummaryResponse,
    tags=[TAG],
    operation_id="labs_group12_validation_summary",
    summary="Get validation summary",
    responses={
        404: {"description": "Submission not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def validation_summary(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ValidationSummaryResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    _submission_or_404(db, submission_id)
    rows = list(
        db.execute(
            select(ValidationResult)
            .where(ValidationResult.submission_id == submission_id)
            .order_by(ValidationResult.check_name.asc())
        )
        .scalars()
        .all()
    )
    return ValidationSummaryResponse(
        submission_id=submission_id,
        overall_status=_overall_status(rows),
        checks=[ValidationResultResponse.model_validate(row) for row in rows],
    )


@router.post(
    f"{PREFIX}/submissions/{{submission_id}}/approve",
    response_model=ModelSubmissionResponse,
    tags=[TAG],
    operation_id="labs_group12_approve_submission",
    summary="Approve a submission when validations pass",
    responses={
        404: {"description": "Submission not found"},
        409: {"description": "Validation failures"},
        422: {"description": "Invalid scenario"},
    },
)
async def approve_submission(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ModelSubmissionResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    submission = _submission_or_404(db, submission_id)
    rows = list(
        db.execute(
            select(ValidationResult).where(
                ValidationResult.submission_id == submission_id
            )
        )
        .scalars()
        .all()
    )
    failing = sorted(row.check_name for row in rows if row.status == "FAIL")
    if failing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"failing_checks": failing}
        )
    submission.status = "APROVADO"
    db.commit()
    create_event(
        db,
        "lab_group12_submission_approved",
        x_lab_group,
        "model_submission",
        submission_id,
        {"group": "12"},
    )
    return ModelSubmissionResponse.model_validate(submission)


@router.post(
    f"{PREFIX}/submissions/{{submission_id}}/deploy",
    response_model=DeploymentResponse,
    tags=[TAG],
    operation_id="labs_group12_deploy_submission",
    summary="Deploy an approved submission",
    responses={
        404: {"description": "Submission not found"},
        409: {"description": "Validation or approval gate failed"},
        422: {"description": "Invalid scenario"},
    },
)
async def deploy_submission(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> DeploymentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    submission = _submission_or_404(db, submission_id)
    rows = list(
        db.execute(
            select(ValidationResult).where(
                ValidationResult.submission_id == submission_id
            )
        )
        .scalars()
        .all()
    )
    failing = sorted(row.check_name for row in rows if row.status == "FAIL")
    if submission.status != "APROVADO" or failing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"failing_checks": failing, "status": submission.status},
        )
    deployment = Deployment(
        id=_next_id(db, Deployment, "id", "DEP"),
        model_id=submission.modelo_id,
        environment=submission.target_env,
        deployed_at=LAB_NOW,
        status="CONCLUIDO",
        replicas=2,
        endpoint=f"https://ml.example/{submission.modelo_id}",
    )
    db.add(deployment)
    db.add(
        JiraTicket(
            id=_next_id(db, JiraTicket, "id", "JIR"),
            submission_id=submission_id,
            key=f"ML-{2000 + int(submission_id.rsplit('-', maxsplit=1)[1])}",
            summary=f"Deploy {submission.modelo_id}",
            status="ABERTO",
            created_at=LAB_NOW,
        )
    )
    db.add(
        ModelNotification(
            id=_next_id(db, ModelNotification, "id", "NTF"),
            submission_id=submission_id,
            destino=submission.owner,
            canal="email",
            mensagem=f"Deploy do modelo {submission.modelo_id} concluido.",
            enviado_em=LAB_NOW,
            lida=False,
        )
    )
    submission.status = "DEPLOYADO"
    db.commit()
    create_event(
        db,
        "lab_group12_submission_deployed",
        x_lab_group,
        "deployment",
        deployment.id,
        {"group": "12"},
    )
    return DeploymentResponse.model_validate(deployment)


@router.post(
    f"{PREFIX}/deployments/{{deployment_id}}/rollback",
    response_model=DeploymentResponse,
    tags=[TAG],
    operation_id="labs_group12_rollback_deployment",
    summary="Rollback a deployment",
    responses={
        404: {"description": "Deployment not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def rollback_deployment(
    deployment_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> DeploymentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    deployment = _deployment_or_404(db, deployment_id)
    deployment.status = "ROLLBACK"
    db.commit()
    create_event(
        db,
        "lab_group12_deployment_rollback",
        x_lab_group,
        "deployment",
        deployment.id,
        {"group": "12"},
    )
    return DeploymentResponse.model_validate(deployment)


@router.get(
    f"{PREFIX}/submissions/{{submission_id}}/artifacts/{{artifact_id}}/download",
    tags=[TAG],
    operation_id="labs_group12_download_artifact",
    summary="Download a deterministic binary artifact",
    responses={
        404: {"description": "Submission or artifact not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def download_artifact(
    submission_id: str,
    artifact_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> Response:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    submission = _submission_or_404(db, submission_id)
    artifact = _artifact_or_404(db, artifact_id)
    if artifact.submission_id != submission_id:
        raise entity_not_found("ModelArtifact", artifact_id)
    payload = build_model_binary(
        artifact.id, submission.modelo_id, submission.version, artifact.size_bytes
    )
    return Response(
        content=payload,
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "Content-Length": str(len(payload)),
        },
    )


@router.get(
    f"{PREFIX}/submissions/{{submission_id}}/model-card",
    tags=[TAG],
    operation_id="labs_group12_download_model_card",
    summary="Download the deterministic model card markdown",
    responses={
        404: {"description": "Submission not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def download_model_card(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> Response:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    submission = _submission_or_404(db, submission_id)
    card = db.execute(
        select(ModelCard).where(ModelCard.model_id == submission.modelo_id).limit(1)
    ).scalar_one()
    payload = build_model_card_md(
        {
            "modelo_id": submission.modelo_id,
            "versao": submission.version,
            "purpose": card.intended_use,
            "owner": submission.owner,
            "dataset": submission.target_env,
            "limitations": card.limitations,
            "pii_documented": submission.data_classificacao,
            "dependencies": submission.framework,
            "approvals": card.approved_by or "pendente",
        }
    )
    return Response(
        content=payload,
        media_type="text/markdown",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{submission.modelo_id}-model-card.md"'
            ),
            "Content-Length": str(len(payload)),
        },
    )


@router.get(
    f"{PREFIX}/submissions/{{submission_id}}/feature-schema",
    tags=[TAG],
    operation_id="labs_group12_download_feature_schema",
    summary="Download the deterministic feature schema YAML",
    responses={
        404: {"description": "Submission not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def download_feature_schema(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> Response:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    submission = _submission_or_404(db, submission_id)
    rows = list(
        db.execute(
            select(FeatureSchema)
            .where(FeatureSchema.submission_id == submission_id)
            .order_by(FeatureSchema.feature_name.asc())
        )
        .scalars()
        .all()
    )
    payload = build_schema_yaml(
        {
            "submission_id": submission_id,
            "modelo_id": submission.modelo_id,
            "features": [
                {
                    "feature_name": row.feature_name,
                    "dtype": row.dtype,
                    "nullable": row.nullable,
                    "min_value": row.min_value,
                    "max_value": row.max_value,
                    "examples": row.examples,
                }
                for row in rows
            ],
        }
    )
    return Response(
        content=payload,
        media_type="application/yaml",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{submission.modelo_id}-schema.yaml"'
            ),
            "Content-Length": str(len(payload)),
        },
    )


@router.get(
    f"{PREFIX}/submissions/{{submission_id}}/metrics",
    tags=[TAG],
    operation_id="labs_group12_download_metrics",
    summary="Download the deterministic metrics JSON",
    responses={
        404: {"description": "Submission not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def download_metrics(
    submission_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> Response:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    _submission_or_404(db, submission_id)
    rows = list(
        db.execute(select(Metrics).where(Metrics.submission_id == submission_id))
        .scalars()
        .all()
    )
    payload = build_metrics_json({row.metric_name: row.metric_value for row in rows})
    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{submission_id}-metrics.json"'
            ),
            "Content-Length": str(len(payload)),
        },
    )


@router.get(
    f"{PREFIX}/model-stats",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group12_stats",
    summary="Get model handover aggregates",
    responses={422: {"description": "Invalid scenario"}},
)
async def get_stats(
    scenario: Scenario = None,
    group: LabGroup = Group12,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    rows = list(db.execute(select(ModelSubmission)).scalars().all())
    return {
        "submissions": len(rows),
        "by_status": {
            value: sum(1 for row in rows if row.status == value)
            for value in sorted({row.status for row in rows})
        },
        "by_framework": {
            value: sum(1 for row in rows if row.framework == value)
            for value in sorted({row.framework for row in rows})
        },
        "by_target_env": {
            value: sum(1 for row in rows if row.target_env == value)
            for value in sorted({row.target_env for row in rows})
        },
    }
