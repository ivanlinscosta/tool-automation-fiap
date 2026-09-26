import json

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.deps import (
    InstructorKey,
    LABS_GROUP_PATH,
    LabGroupHeader,
    Scenario,
    entity_not_found,
    require_group,
    require_instructor_key,
    scenario_or_422,
)
from ....labs.generators import LAB_NOW
from ....labs.pagination import apply_sort, build_page, page_params
from ....labs.pdf import build_evidence_pdf
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group11_evidences import (
    ActionPlan,
    ActionPlanCompleteRequest,
    ActionPlanCreate,
    ActionPlanResponse,
    EvidenceAnalysisResponse,
    EvidenceInstructorResponse,
    EvidenceRegistry,
    EvidenceRegistryResponse,
    EvidenceReviewRequest,
    IncomingEmail,
    IncomingEmailCreate,
    IncomingEmailResponse,
    RestoreEvidence,
    RestoreEvidenceCreate,
    RestoreEvidenceResponse,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 11"
Group11 = Depends(require_group(11))
EXPECTED_VERSIONS = {"erp": "2.4.1", "crm": "5.9.0", "dw": "3.2.4", "billing": "1.18.7"}


def _next_id(db: Session, model: type, field_name: str, prefix: str) -> str:
    field = getattr(model, field_name)
    highest = db.execute(
        select(field).order_by(field.desc()).limit(1)
    ).scalar_one_or_none()
    if highest is None:
        return f"{prefix}-000001"
    return f"{prefix}-{int(str(highest).rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _email_or_404(db: Session, email_id: str) -> IncomingEmail:
    row = db.get(IncomingEmail, email_id)
    if row is None:
        raise entity_not_found("IncomingEmail", email_id)
    return row


def _evidence_or_404(db: Session, evidence_id: str) -> RestoreEvidence:
    row = db.get(RestoreEvidence, evidence_id)
    if row is None:
        raise entity_not_found("RestoreEvidence", evidence_id)
    return row


def _action_plan_or_404(db: Session, action_plan_id: str) -> ActionPlan:
    row = db.get(ActionPlan, action_plan_id)
    if row is None:
        raise entity_not_found("ActionPlan", action_plan_id)
    return row


def _analysis_for_payload(
    sistema: str, versao_depois: str | None, observacoes: str | None, resultado: str
) -> tuple[list[str], list[str], str, str]:
    divergent_fields: list[str] = []
    missing_fields: list[str] = []
    if versao_depois != EXPECTED_VERSIONS[sistema]:
        divergent_fields.append("versao_depois")
    if sistema in {"erp", "billing"} and not observacoes:
        missing_fields.append("observacoes")
    if resultado != "SUCESSO":
        divergent_fields.append("resultado")
    decisao = "APROVADO" if not divergent_fields and not missing_fields else "REPROVADO"
    rationale = (
        "Evidencia aderente ao restore esperado."
        if decisao == "APROVADO"
        else "Evidencia com divergencias ou campos obrigatorios ausentes."
    )
    return divergent_fields, missing_fields, decisao, rationale


def _analysis_response(row: RestoreEvidence) -> EvidenceAnalysisResponse:
    return EvidenceAnalysisResponse(
        evidence_id=row.evidence_id,
        IC=row.IC,
        has_prints=row.has_prints,
        divergent_fields=json.loads(row.divergent_fields_json),
        missing_fields=json.loads(row.missing_fields_json),
    )


@router.get(
    f"{PREFIX}/emails",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group11_list_emails",
    summary="List incoming emails",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_emails(
    scenario: Scenario = None,
    group: LabGroup = Group11,
    severidade: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default="email_id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(IncomingEmail)
    if severidade:
        query = query.where(IncomingEmail.severidade == severidade)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(IncomingEmail.assunto).like(pattern),
                func.lower(IncomingEmail.corpo).like(pattern),
                func.lower(IncomingEmail.ticket_mudanca).like(pattern),
            )
        )
    query = apply_sort(query, IncomingEmail, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: IncomingEmailResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/emails/{{email_id}}",
    response_model=IncomingEmailResponse,
    tags=[TAG],
    operation_id="labs_group11_get_email",
    summary="Get one incoming email",
    responses={
        404: {"description": "Email not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def get_email(
    email_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> IncomingEmailResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return IncomingEmailResponse.model_validate(_email_or_404(db, email_id))


@router.get(
    f"{PREFIX}/evidence",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group11_list_evidence",
    summary="List restore evidence",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_evidence(
    scenario: Scenario = None,
    group: LabGroup = Group11,
    resultado: str | None = Query(default=None),
    sistema: str | None = Query(default=None),
    severidade: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default="evidence_id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(RestoreEvidence)
    if severidade:
        query = query.join(
            IncomingEmail, IncomingEmail.email_id == RestoreEvidence.email_id
        ).where(IncomingEmail.severidade == severidade)
    if resultado:
        query = query.where(RestoreEvidence.resultado == resultado)
    if sistema:
        query = query.where(RestoreEvidence.sistema == sistema)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(RestoreEvidence.IC).like(pattern),
                func.lower(RestoreEvidence.sistema).like(pattern),
                func.lower(RestoreEvidence.observacoes).like(pattern),
            )
        )
    query = apply_sort(query, RestoreEvidence, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: RestoreEvidenceResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/evidence/{{evidence_id}}",
    response_model=RestoreEvidenceResponse,
    tags=[TAG],
    operation_id="labs_group11_get_evidence",
    summary="Get one evidence",
    responses={
        404: {"description": "Evidence not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def get_evidence(
    evidence_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> RestoreEvidenceResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return RestoreEvidenceResponse.model_validate(_evidence_or_404(db, evidence_id))


@router.get(
    f"{PREFIX}/registry",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group11_list_registry",
    summary="List evidence registry rows",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_registry(
    scenario: Scenario = None,
    group: LabGroup = Group11,
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
    query = select(EvidenceRegistry)
    if status_filter:
        query = query.where(EvidenceRegistry.status == status_filter)
    query = apply_sort(query, EvidenceRegistry, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: EvidenceRegistryResponse.model_validate(
            row
        ).model_dump(),
    )


@router.get(
    f"{PREFIX}/action-plans",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group11_list_action_plans",
    summary="List action plans",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_action_plans(
    scenario: Scenario = None,
    group: LabGroup = Group11,
    evidence_id: str | None = Query(default=None),
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
    query = select(ActionPlan)
    if evidence_id:
        query = query.where(ActionPlan.evidence_id == evidence_id)
    if status_filter:
        query = query.where(ActionPlan.status == status_filter)
    query = apply_sort(query, ActionPlan, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: ActionPlanResponse.model_validate(row).model_dump(),
    )


@router.post(
    f"{PREFIX}/emails",
    response_model=IncomingEmailResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group11_create_email",
    summary="Intake one email",
    responses={422: {"description": "Validation error"}},
)
async def create_email(
    payload: IncomingEmailCreate,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> IncomingEmailResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    row = IncomingEmail(
        email_id=_next_id(db, IncomingEmail, "email_id", "EML"),
        remetente=payload.remetente,
        assunto=payload.assunto,
        corpo=payload.corpo,
        recebido_em=payload.recebido_em or LAB_NOW,
        ticket_mudanca=payload.ticket_mudanca,
        severidade=payload.severidade,
    )
    db.add(row)
    db.commit()
    create_event(
        db,
        "lab_group11_email_created",
        x_lab_group,
        "incoming_email",
        row.email_id,
        {"group": "11"},
    )
    return IncomingEmailResponse.model_validate(row)


@router.post(
    f"{PREFIX}/emails/{{email_id}}/evidence",
    response_model=RestoreEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group11_create_evidence",
    summary="Attach evidence to one email",
    responses={
        404: {"description": "Email not found"},
        422: {"description": "Validation error"},
    },
)
async def create_evidence(
    email_id: str,
    payload: RestoreEvidenceCreate,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> RestoreEvidenceResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    _email_or_404(db, email_id)
    divergent_fields, missing_fields, decisao, rationale = _analysis_for_payload(
        payload.sistema, payload.versao_depois, payload.observacoes, payload.resultado
    )
    row = RestoreEvidence(
        evidence_id=_next_id(db, RestoreEvidence, "evidence_id", "EVD"),
        email_id=email_id,
        IC=payload.IC,
        data_hora_teste=payload.data_hora_teste,
        resultado=payload.resultado,
        sistema=payload.sistema,
        versao_antes=payload.versao_antes,
        versao_depois=payload.versao_depois,
        duracao_seg=payload.duracao_seg,
        responsavel=payload.responsavel,
        observacoes=payload.observacoes,
        has_prints=payload.has_prints,
        divergent_fields_json=json.dumps(
            divergent_fields, ensure_ascii=False, sort_keys=True
        ),
        missing_fields_json=json.dumps(
            missing_fields, ensure_ascii=False, sort_keys=True
        ),
        decisao=decisao,
        rationale=rationale,
    )
    db.add(row)
    db.commit()
    create_event(
        db,
        "lab_group11_evidence_created",
        x_lab_group,
        "restore_evidence",
        row.evidence_id,
        {"group": "11", "ic": row.IC},
    )
    return RestoreEvidenceResponse.model_validate(row)


@router.get(
    f"{PREFIX}/evidence/{{evidence_id}}/analysis",
    response_model=EvidenceAnalysisResponse,
    tags=[TAG],
    operation_id="labs_group11_evidence_analysis",
    summary="Get deterministic divergence analysis",
    responses={
        404: {"description": "Evidence not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def evidence_analysis(
    evidence_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> EvidenceAnalysisResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return _analysis_response(_evidence_or_404(db, evidence_id))


@router.post(
    f"{PREFIX}/evidence/{{evidence_id}}/review",
    response_model=EvidenceRegistryResponse,
    tags=[TAG],
    operation_id="labs_group11_review_evidence",
    summary="Record the registry review of one evidence",
    responses={
        404: {"description": "Evidence not found"},
        422: {"description": "Validation error"},
    },
)
async def review_evidence(
    evidence_id: str,
    payload: EvidenceReviewRequest,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> EvidenceRegistryResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    evidence = _evidence_or_404(db, evidence_id)
    existing = db.execute(
        select(EvidenceRegistry).where(EvidenceRegistry.IC == evidence.IC).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return EvidenceRegistryResponse.model_validate(existing)
    row = EvidenceRegistry(
        id=_next_id(db, EvidenceRegistry, "id", "REG"),
        IC=evidence.IC,
        status=payload.status,
        analisado_por=payload.analisado_por,
        analisado_em=LAB_NOW,
        parecer=payload.parecer,
    )
    db.add(row)
    db.commit()
    create_event(
        db,
        "lab_group11_evidence_reviewed",
        x_lab_group,
        "evidence_registry",
        row.id,
        {"group": "11", "ic": row.IC},
    )
    return EvidenceRegistryResponse.model_validate(row)


@router.post(
    f"{PREFIX}/evidence/{{evidence_id}}/action-plans",
    response_model=ActionPlanResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group11_create_action_plan",
    summary="Create an action plan for one evidence",
    responses={
        404: {"description": "Evidence not found"},
        422: {"description": "Validation error"},
    },
)
async def create_action_plan(
    evidence_id: str,
    payload: ActionPlanCreate,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ActionPlanResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    _evidence_or_404(db, evidence_id)
    row = ActionPlan(
        id=_next_id(db, ActionPlan, "id", "ACT"),
        evidence_id=evidence_id,
        acao=payload.acao,
        prazo=payload.prazo,
        responsavel=payload.responsavel,
        status="PENDENTE",
        conclusao=None,
        created_at=LAB_NOW,
        concluded_at=None,
    )
    db.add(row)
    db.commit()
    create_event(
        db,
        "lab_group11_action_plan_created",
        x_lab_group,
        "action_plan",
        row.id,
        {"group": "11"},
    )
    return ActionPlanResponse.model_validate(row)


@router.post(
    f"{PREFIX}/action-plans/{{action_plan_id}}/complete",
    response_model=ActionPlanResponse,
    tags=[TAG],
    operation_id="labs_group11_complete_action_plan",
    summary="Complete an action plan",
    responses={
        404: {"description": "Action plan not found"},
        422: {"description": "Validation error"},
    },
)
async def complete_action_plan(
    action_plan_id: str,
    payload: ActionPlanCompleteRequest,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> ActionPlanResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    row = _action_plan_or_404(db, action_plan_id)
    row.status = "CONCLUIDA"
    row.conclusao = payload.conclusao
    row.concluded_at = LAB_NOW
    db.commit()
    create_event(
        db,
        "lab_group11_action_plan_completed",
        x_lab_group,
        "action_plan",
        row.id,
        {"group": "11"},
    )
    return ActionPlanResponse.model_validate(row)


@router.get(
    f"{PREFIX}/evidence/{{evidence_id}}/pdf",
    tags=[TAG],
    operation_id="labs_group11_evidence_pdf",
    summary="Download one deterministic evidence PDF",
    responses={
        404: {"description": "Evidence not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def evidence_pdf(
    evidence_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> Response:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    row = _evidence_or_404(db, evidence_id)
    email = _email_or_404(db, row.email_id)
    payload = build_evidence_pdf(
        evidence_id=row.evidence_id,
        ic=row.IC,
        ticket_mudanca=email.ticket_mudanca,
        data_hora_teste=row.data_hora_teste.isoformat(),
        resultado=row.resultado,
        has_prints=row.has_prints,
        divergent_fields=json.loads(row.divergent_fields_json),
        missing_fields=json.loads(row.missing_fields_json),
    )
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="evidencia-{row.evidence_id}.pdf"'
            ),
            "Content-Length": str(len(payload)),
        },
    )


@router.get(
    f"{PREFIX}/instructor/evidence/{{evidence_id}}",
    response_model=EvidenceInstructorResponse,
    tags=[TAG],
    operation_id="labs_group11_instructor_get_evidence",
    summary="Instructor only: reveal evidence ground truth",
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled"},
        404: {"description": "Evidence not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def instructor_get_evidence(
    evidence_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> EvidenceInstructorResponse:
    await apply_scenario(scenario_or_422(scenario))
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    row = _evidence_or_404(db, evidence_id)
    body = RestoreEvidenceResponse.model_validate(row).model_dump()
    body["decisao"] = row.decisao
    body["rationale"] = row.rationale
    body["divergent_fields"] = json.loads(row.divergent_fields_json)
    body["missing_fields"] = json.loads(row.missing_fields_json)
    return EvidenceInstructorResponse(**body)


@router.get(
    f"{PREFIX}/evidence-stats",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group11_stats",
    summary="Get evidence aggregates",
    responses={422: {"description": "Invalid scenario"}},
)
async def get_stats(
    scenario: Scenario = None,
    group: LabGroup = Group11,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    evidence_rows = list(db.execute(select(RestoreEvidence)).scalars().all())
    registry_rows = list(db.execute(select(EvidenceRegistry)).scalars().all())
    return {
        "evidence": len(evidence_rows),
        "by_resultado": {
            value: sum(1 for row in evidence_rows if row.resultado == value)
            for value in sorted({row.resultado for row in evidence_rows})
        },
        "by_sistema": {
            value: sum(1 for row in evidence_rows if row.sistema == value)
            for value in sorted({row.sistema for row in evidence_rows})
        },
        "by_status": {
            value: sum(1 for row in registry_rows if row.status == value)
            for value in sorted({row.status for row in registry_rows})
        },
    }
