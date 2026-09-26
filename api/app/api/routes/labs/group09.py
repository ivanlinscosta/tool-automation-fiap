
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from ....labs.generators import LAB_NOW, is_valid_cpf
from ....labs.pagination import apply_sort, build_page, page_params
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group09_onboarding import (
    AccessMatrix,
    AccessMatrixCreate,
    AccessMatrixResponse,
    Candidate,
    CandidateCreate,
    CandidateInstructorResponse,
    CandidateResponse,
    Equipment,
    EquipmentCreate,
    EquipmentResponse,
    Onboarding,
    OnboardingResponse,
    OnboardingStatusResponse,
    OnboardingTask,
    OnboardingTaskResponse,
    SecurityApproval,
    SecurityApprovalCreate,
    SecurityApprovalResponse,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 09"
Group09 = Depends(require_group(9))


def _candidate_or_404(db: Session, candidate_id: str) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise entity_not_found("Candidate", candidate_id)
    return candidate


def _equipment_or_404(db: Session, equipment_id: str) -> Equipment:
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise entity_not_found("Equipment", equipment_id)
    return equipment


def _next_id(db: Session, model: type, field_name: str, prefix: str) -> str:
    field = getattr(model, field_name)
    highest = db.execute(
        select(field).order_by(field.desc()).limit(1)
    ).scalar_one_or_none()
    if highest is None:
        return f"{prefix}-000001"
    return f"{prefix}-{int(str(highest).rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _security_cleared(db: Session, candidate_id: str) -> bool:
    rows = list(
        db.execute(
            select(SecurityApproval).where(
                SecurityApproval.candidate_id == candidate_id
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return False
    return all(row.status in {"APROVADO", "EXCEPCAO_APROVADA"} for row in rows)


def _child_count(db: Session, model: type, field_name: str, value: str) -> int:
    field = getattr(model, field_name)
    return int(
        db.execute(
            select(func.count()).select_from(model).where(field == value)
        ).scalar_one()
    )


def _status_rollup(db: Session, candidate_id: str) -> OnboardingStatusResponse:
    candidate = _candidate_or_404(db, candidate_id)
    onboarding = db.execute(
        select(Onboarding).where(Onboarding.id_candidato == candidate_id).limit(1)
    ).scalar_one_or_none()
    approvals = list(
        db.execute(
            select(SecurityApproval).where(
                SecurityApproval.candidate_id == candidate_id
            )
        )
        .scalars()
        .all()
    )
    equipment_rows = list(
        db.execute(select(Equipment).where(Equipment.candidate_id == candidate_id))
        .scalars()
        .all()
    )
    access_rows = list(
        db.execute(
            select(AccessMatrix).where(AccessMatrix.candidate_id == candidate_id)
        )
        .scalars()
        .all()
    )
    task_rows = list(
        db.execute(
            select(OnboardingTask).where(OnboardingTask.candidate_id == candidate_id)
        )
        .scalars()
        .all()
    )
    return OnboardingStatusResponse(
        candidate_id=candidate_id,
        status_candidato=candidate.status,
        security_total=len(approvals),
        security_cleared=sum(
            1 for row in approvals if row.status in {"APROVADO", "EXCEPCAO_APROVADA"}
        ),
        equipment_total=len(equipment_rows),
        equipment_issued=sum(1 for row in equipment_rows if row.status == "EMPRESTADO"),
        access_total=len(access_rows),
        access_admin_total=sum(1 for row in access_rows if row.nivel_acesso == "ADMIN"),
        tasks_total=len(task_rows),
        tasks_completed=sum(1 for row in task_rows if row.concluida),
        onboarding_status=onboarding.status if onboarding is not None else None,
    )


@router.get(
    f"{PREFIX}/candidates",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group09_list_candidates",
    summary="List HR onboarding candidates",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_candidates(
    scenario: Scenario = None,
    group: LabGroup = Group09,
    status_filter: str | None = Query(default=None, alias="status"),
    departamento: str | None = Query(default=None),
    admissao_excecao: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default="id_candidato"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Candidate)
    if status_filter:
        query = query.where(Candidate.status == status_filter)
    if departamento:
        query = query.where(Candidate.departamento == departamento)
    if admissao_excecao is not None:
        query = query.where(Candidate.admissao_excecao.is_(admissao_excecao))
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Candidate.nome).like(pattern),
                func.lower(Candidate.email).like(pattern),
                func.lower(Candidate.cargo).like(pattern),
                func.lower(Candidate.cpf).like(pattern),
            )
        )
    query = apply_sort(query, Candidate, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: CandidateResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/candidates/{{candidate_id}}",
    response_model=CandidateResponse,
    tags=[TAG],
    operation_id="labs_group09_get_candidate",
    summary="Get one candidate",
    responses={
        404: {"description": "Candidate not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def get_candidate(
    candidate_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CandidateResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return CandidateResponse.model_validate(_candidate_or_404(db, candidate_id))


@router.get(
    f"{PREFIX}/onboardings",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group09_list_onboardings",
    summary="List onboarding records",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_onboardings(
    scenario: Scenario = None,
    group: LabGroup = Group09,
    candidate_id: str | None = Query(default=None),
    sort: str | None = Query(default="id_onboarding"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(Onboarding)
    if candidate_id:
        query = query.where(Onboarding.id_candidato == candidate_id)
    query = apply_sort(query, Onboarding, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: OnboardingResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/access-matrix",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group09_list_access_matrix",
    summary="List access matrix rows",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_access_matrix(
    scenario: Scenario = None,
    group: LabGroup = Group09,
    candidate_id: str | None = Query(default=None),
    nivel_acesso: str | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(AccessMatrix)
    if candidate_id:
        query = query.where(AccessMatrix.candidate_id == candidate_id)
    if nivel_acesso:
        query = query.where(AccessMatrix.nivel_acesso == nivel_acesso)
    query = apply_sort(query, AccessMatrix, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: AccessMatrixResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/equipment",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group09_list_equipment",
    summary="List requested equipment",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_equipment(
    scenario: Scenario = None,
    group: LabGroup = Group09,
    candidate_id: str | None = Query(default=None),
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
    query = select(Equipment)
    if candidate_id:
        query = query.where(Equipment.candidate_id == candidate_id)
    if status_filter:
        query = query.where(Equipment.status == status_filter)
    query = apply_sort(query, Equipment, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: EquipmentResponse.model_validate(row).model_dump(),
    )


@router.get(
    f"{PREFIX}/security-approvals",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group09_list_security_approvals",
    summary="List security approval rows",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_security_approvals(
    scenario: Scenario = None,
    group: LabGroup = Group09,
    candidate_id: str | None = Query(default=None),
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
    query = select(SecurityApproval)
    if candidate_id:
        query = query.where(SecurityApproval.candidate_id == candidate_id)
    if status_filter:
        query = query.where(SecurityApproval.status == status_filter)
    query = apply_sort(query, SecurityApproval, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: SecurityApprovalResponse.model_validate(
            row
        ).model_dump(),
    )


@router.get(
    f"{PREFIX}/tasks",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group09_list_tasks",
    summary="List onboarding tasks",
    responses={
        400: {"description": "Invalid sort field"},
        422: {"description": "Invalid scenario"},
    },
)
async def list_tasks(
    scenario: Scenario = None,
    group: LabGroup = Group09,
    candidate_id: str | None = Query(default=None),
    concluida: bool | None = Query(default=None),
    sort: str | None = Query(default="id"),
    order: str | None = Query(default=None),
    page: tuple[int, int] = Depends(page_params),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    limit, offset = page
    query = select(OnboardingTask)
    if candidate_id:
        query = query.where(OnboardingTask.candidate_id == candidate_id)
    if concluida is not None:
        query = query.where(OnboardingTask.concluida.is_(concluida))
    query = apply_sort(query, OnboardingTask, sort, order)
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda row: OnboardingTaskResponse.model_validate(row).model_dump(),
    )


@router.post(
    f"{PREFIX}/candidates",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group09_create_candidate",
    summary="Create a candidate intake record",
    responses={
        201: {"description": "Candidate created"},
        422: {"description": "Validation error"},
    },
)
async def create_candidate(
    payload: CandidateCreate,
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CandidateResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if payload.admissao_excecao and not payload.admissao_motivo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="admissao_motivo is required when admissao_excecao=true",
        )
    candidate_id = _next_id(db, Candidate, "id_candidato", "CAND")
    created_at = LAB_NOW
    candidate = Candidate(
        id_candidato=candidate_id,
        nome=payload.nome,
        email=payload.email.strip().lower(),
        cpf=payload.cpf,
        cargo=payload.cargo,
        departamento=payload.departamento,
        data_admissao=payload.data_admissao,
        status="EM_ANALISE",
        admissao_excecao=payload.admissao_excecao,
        admissao_motivo=payload.admissao_motivo,
        decisao_admissao_esperada=payload.decisao_admissao_esperada,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(candidate)
    db.flush()
    db.add(
        Onboarding(
            id_onboarding=_next_id(db, Onboarding, "id_onboarding", "ONB"),
            id_candidato=candidate_id,
            data_inicio=payload.data_admissao,
            data_fim_prevista=payload.data_admissao,
            status="PENDENTE",
            responsavel_rh="rh.intake",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db.flush()
    for position, title in enumerate(
        ("Conferir documentos", "Abrir cadastro RH", "Liberar check de seguranca"),
        start=1,
    ):
        db.add(
            OnboardingTask(
                id=f"TSK-{candidate_id}-{position}",
                candidate_id=candidate_id,
                titulo=title,
                categoria="intake",
                responsavel="rh.intake",
                prazo=created_at,
                concluida=False,
                concluida_em=None,
                ordem=position,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    db.commit()
    create_event(
        db,
        "lab_group09_candidate_created",
        x_lab_group,
        "candidate",
        candidate.id_candidato,
        {"group": "09"},
    )
    return CandidateResponse.model_validate(candidate)


@router.post(
    f"{PREFIX}/candidates/{{candidate_id}}/security-approvals",
    response_model=SecurityApprovalResponse,
    tags=[TAG],
    operation_id="labs_group09_create_security_approval",
    summary="Record a security verification",
    responses={
        404: {"description": "Candidate not found"},
        422: {"description": "Validation error"},
    },
)
async def create_security_approval(
    candidate_id: str,
    payload: SecurityApprovalCreate,
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> SecurityApprovalResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    candidate = _candidate_or_404(db, candidate_id)
    if payload.status == "EXCEPCAO_APROVADA" and not payload.parecer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="parecer is required for EXCEPCAO_APROVADA",
        )
    created_at = LAB_NOW
    approval = SecurityApproval(
        id=(
            f"SAP-{candidate_id}-"
            f"{_child_count(db, SecurityApproval, 'candidate_id', candidate_id) + 1}"
        ),
        candidate_id=candidate_id,
        tipo_verificacao=payload.tipo_verificacao,
        status=payload.status,
        verificado_por=payload.verificado_por,
        verificado_em=LAB_NOW if payload.status != "PENDENTE" else None,
        parecer=payload.parecer,
        created_at=created_at,
        updated_at=created_at,
    )
    candidate.updated_at = created_at
    db.add(approval)
    db.commit()
    create_event(
        db,
        "lab_group09_security_recorded",
        x_lab_group,
        "candidate",
        candidate_id,
        {"group": "09", "tipo": approval.tipo_verificacao},
    )
    return SecurityApprovalResponse.model_validate(approval)


@router.post(
    f"{PREFIX}/candidates/{{candidate_id}}/equipment",
    response_model=EquipmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group09_create_equipment_request",
    summary="Request equipment for a candidate",
    responses={
        404: {"description": "Candidate not found"},
        422: {"description": "Validation error"},
    },
)
async def create_equipment_request(
    candidate_id: str,
    payload: EquipmentCreate,
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> EquipmentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    candidate = _candidate_or_404(db, candidate_id)
    row = Equipment(
        id=(
            f"EQP-{candidate_id}-"
            f"{_child_count(db, Equipment, 'candidate_id', candidate_id) + 1}"
        ),
        candidate_id=candidate_id,
        tipo=payload.tipo,
        modelo=payload.modelo,
        serial=payload.serial,
        status="SOLICITADO",
        solicitacao_motivo=payload.solicitacao_motivo,
        created_at=LAB_NOW,
        updated_at=LAB_NOW,
    )
    candidate.updated_at = LAB_NOW
    db.add(row)
    db.commit()
    create_event(
        db,
        "lab_group09_equipment_requested",
        x_lab_group,
        "equipment",
        row.id,
        {"group": "09", "candidate_id": candidate_id},
    )
    return EquipmentResponse.model_validate(row)


@router.post(
    f"{PREFIX}/equipment/{{equipment_id}}/issue",
    response_model=EquipmentResponse,
    tags=[TAG],
    operation_id="labs_group09_issue_equipment",
    summary="Issue a requested equipment item",
    responses={
        404: {"description": "Equipment not found"},
        409: {"description": "Security not cleared"},
        422: {"description": "Invalid scenario"},
    },
)
async def issue_equipment(
    equipment_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> EquipmentResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    equipment = _equipment_or_404(db, equipment_id)
    if not _security_cleared(db, equipment.candidate_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Security approvals are not fully cleared",
        )
    equipment.status = "EMPRESTADO"
    equipment.updated_at = LAB_NOW
    db.commit()
    create_event(
        db,
        "lab_group09_equipment_issued",
        x_lab_group,
        "equipment",
        equipment.id,
        {"group": "09"},
    )
    return EquipmentResponse.model_validate(equipment)


@router.post(
    f"{PREFIX}/candidates/{{candidate_id}}/access-matrix",
    response_model=AccessMatrixResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group09_create_access_matrix",
    summary="Grant access to a candidate",
    responses={
        404: {"description": "Candidate not found"},
        409: {"description": "Missing approval"},
        422: {"description": "Invalid scenario"},
    },
)
async def create_access_matrix(
    candidate_id: str,
    payload: AccessMatrixCreate,
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> AccessMatrixResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    _candidate_or_404(db, candidate_id)
    if payload.nivel_acesso == "ADMIN":
        approval = db.execute(
            select(SecurityApproval).where(
                SecurityApproval.candidate_id == candidate_id,
                SecurityApproval.tipo_verificacao == "ACESSO_PRECIFICADO",
                SecurityApproval.status.in_(("APROVADO", "EXCEPCAO_APROVADA")),
            )
        ).scalar_one_or_none()
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="ADMIN access requires ACESSO_PRECIFICADO approval",
            )
    row = AccessMatrix(
        id=(
            f"ACC-{candidate_id}-"
            f"{_child_count(db, AccessMatrix, 'candidate_id', candidate_id) + 1}"
        ),
        candidate_id=candidate_id,
        sistema=payload.sistema,
        perfil=payload.perfil,
        nivel_acesso=payload.nivel_acesso,
        aprovado=payload.aprovado,
        aprovador=payload.aprovador,
        data_aprovacao=LAB_NOW if payload.aprovado else None,
        created_at=LAB_NOW,
        updated_at=LAB_NOW,
    )
    db.add(row)
    db.commit()
    create_event(
        db,
        "lab_group09_access_granted",
        x_lab_group,
        "access_matrix",
        row.id,
        {"group": "09", "nivel": row.nivel_acesso},
    )
    return AccessMatrixResponse.model_validate(row)


@router.get(
    f"{PREFIX}/candidates/{{candidate_id}}/onboarding-status",
    response_model=OnboardingStatusResponse,
    tags=[TAG],
    operation_id="labs_group09_get_onboarding_status",
    summary="Get rollup onboarding status for one candidate",
    responses={
        404: {"description": "Candidate not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def get_onboarding_status(
    candidate_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> OnboardingStatusResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return _status_rollup(db, candidate_id)


@router.get(
    f"{PREFIX}/instructor/candidates/{{candidate_id}}",
    response_model=CandidateInstructorResponse,
    tags=[TAG],
    operation_id="labs_group09_instructor_get_candidate",
    summary="Instructor only: get candidate ground truth",
    responses={
        401: {"description": "Missing or invalid X-Instructor-Key"},
        403: {"description": "Instructor endpoints disabled"},
        404: {"description": "Candidate not found"},
        422: {"description": "Invalid scenario"},
    },
)
async def instructor_get_candidate(
    candidate_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> CandidateInstructorResponse:
    await apply_scenario(scenario_or_422(scenario))
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    return CandidateInstructorResponse.model_validate(
        _candidate_or_404(db, candidate_id)
    )


@router.get(
    f"{PREFIX}/onboarding-stats",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group09_stats",
    summary="Get onboarding aggregates",
    responses={422: {"description": "Invalid scenario"}},
)
async def get_stats(
    scenario: Scenario = None,
    group: LabGroup = Group09,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    candidates = list(db.execute(select(Candidate)).scalars().all())
    return {
        "total_candidates": len(candidates),
        "by_status": {
            value: sum(1 for row in candidates if row.status == value)
            for value in sorted({row.status for row in candidates})
        },
        "by_departamento": {
            value: sum(1 for row in candidates if row.departamento == value)
            for value in sorted({row.departamento for row in candidates})
        },
        "admissao_excecao": sum(1 for row in candidates if row.admissao_excecao),
        "cpfs_validos": sum(1 for row in candidates if is_valid_cpf(row.cpf)),
    }
