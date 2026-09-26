
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.deps import (
    LABS_GROUP_PATH,
    LabGroupHeader,
    Scenario,
    entity_not_found,
    require_group,
    scenario_or_422,
)
from ....labs.generators import LAB_NOW
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....labs.xlsx import build_xlsx
from ....models.labs.group02_rates import (
    FILE_STATUSES,
    IngestionFile,
    IngestionFileCreate,
    IngestionFileResponse,
    PrimaryMarketRate,
    PrimaryMarketRateResponse,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 02"
Group02 = Depends(require_group(2))
RATE_SORT_FIELDS = (
    "rate_id",
    "mes",
    "indexador",
    "status",
    "taxa",
    "vencimento",
    "created_at",
    "updated_at",
)
FILE_SORT_FIELDS = (
    "file_id",
    "nome_arquivo",
    "status",
    "records_valid",
    "records_invalid",
    "created_at",
    "updated_at",
)

_GROUP02_422 = {
    "description": (
        "Simulated validation error requested via ?scenario=validation_error"
    ),
    "content": {
        "application/json": {"example": {"detail": "Simulated validation error"}}
    },
}


def _rate_or_404(db: Session, rate_id: str) -> PrimaryMarketRate:
    rate = db.get(PrimaryMarketRate, rate_id)
    if rate is None:
        raise entity_not_found("PrimaryMarketRate", rate_id)
    return rate


def _file_or_404(db: Session, file_id: str) -> IngestionFile:
    file_record = db.get(IngestionFile, file_id)
    if file_record is None:
        raise entity_not_found("IngestionFile", file_id)
    return file_record


def _next_file_id(db: Session) -> str:
    highest = db.execute(
        select(IngestionFile.file_id).order_by(IngestionFile.file_id.desc()).limit(1)
    ).scalar_one_or_none()
    if highest is None:
        return "FILE-0001"
    return f"FILE-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:04d}"


@router.get(
    f"{PREFIX}/rates",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group02_list_rates",
    summary="List primary market rates with filters, sorting and pagination",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP02_422},
)
async def list_rates(
    scenario: Scenario = None,
    group: LabGroup = Group02,
    indexador: str | None = Query(default=None, description="Filter by indexer name."),
    mes: str | None = Query(
        default=None, description="Filter by competence month in YYYY-MM format."
    ),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by row status."
    ),
    search: str | None = Query(
        default=None,
        description=(
            "Case-insensitive search on emissor, cnpj, indexador or observacao."
        ),
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(RATE_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(PrimaryMarketRate)
    if indexador:
        query = query.where(PrimaryMarketRate.indexador == indexador)
    if mes:
        query = query.where(PrimaryMarketRate.mes == mes)
    if status_filter:
        query = query.where(PrimaryMarketRate.status == status_filter)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(PrimaryMarketRate.emissor).like(pattern),
                func.lower(PrimaryMarketRate.cnpj).like(pattern),
                func.lower(PrimaryMarketRate.indexador).like(pattern),
                func.lower(func.coalesce(PrimaryMarketRate.observacao, "")).like(
                    pattern
                ),
            )
        )
    query = (
        apply_sort(query, PrimaryMarketRate, sort, order)
        if sort
        else query.order_by(PrimaryMarketRate.rate_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: PrimaryMarketRateResponse.model_validate(
            item
        ).model_dump(),
    )


@router.get(
    f"{PREFIX}/rates/{{rate_id}}",
    response_model=PrimaryMarketRateResponse,
    tags=[TAG],
    operation_id="labs_group02_get_rate",
    summary="Get one primary market rate by id",
    responses={404: {"description": "Rate not found"}, 422: _GROUP02_422},
)
async def get_rate(
    rate_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group02,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PrimaryMarketRateResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return PrimaryMarketRateResponse.model_validate(_rate_or_404(db, rate_id))


@router.get(
    f"{PREFIX}/files",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group02_list_files",
    summary="List ingestion files and their processing status",
    responses={400: {"description": "Invalid sort field"}, 422: _GROUP02_422},
)
async def list_files(
    scenario: Scenario = None,
    group: LabGroup = Group02,
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by file processing status."
    ),
    sort: str | None = Query(
        default=None, description=f"One of: {', '.join(FILE_SORT_FIELDS)}."
    ),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(IngestionFile)
    if status_filter:
        query = query.where(IngestionFile.status == status_filter)
    query = (
        apply_sort(query, IngestionFile, sort, order)
        if sort
        else query.order_by(IngestionFile.file_id.asc())
    )
    return build_page(
        db,
        query,
        limit,
        offset,
        serializer=lambda item: IngestionFileResponse.model_validate(item).model_dump(),
    )


@router.post(
    f"{PREFIX}/files",
    response_model=IngestionFileResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group02_create_file",
    summary="Register a new ingestion file record",
    responses={422: _GROUP02_422},
)
async def create_file(
    payload: IngestionFileCreate,
    scenario: Scenario = None,
    group: LabGroup = Group02,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> IngestionFileResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if payload.status not in FILE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown file status '{payload.status}'",
        )
    moment = min(payload.created_at or LAB_NOW, LAB_NOW)
    file_record = IngestionFile(
        file_id=_next_file_id(db),
        nome_arquivo=payload.nome_arquivo,
        origem=payload.origem,
        status=payload.status,
        records_valid=0,
        records_invalid=0,
        created_at=moment,
        updated_at=moment,
    )
    db.add(file_record)
    db.commit()
    create_event(
        db,
        event_type="lab_group02_file_created",
        lab_group=x_lab_group,
        resource_type="lab_ingestion_file",
        resource_id=file_record.file_id,
        metadata={
            "status": file_record.status,
            "group": "02",
            "origem": file_record.origem,
        },
    )
    return IngestionFileResponse.model_validate(file_record)


@router.get(
    f"{PREFIX}/files/{{file_id}}/download",
    tags=[TAG],
    operation_id="labs_group02_download_file",
    summary="Download the deterministic XLSX payload for one ingestion file",
    responses={404: {"description": "File not found"}, 422: _GROUP02_422},
)
async def download_file(
    file_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group02,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> Response:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    file_record = _file_or_404(db, file_id)
    rows = list(
        db.execute(
            select(PrimaryMarketRate)
            .where(PrimaryMarketRate.file_id == file_id)
            .order_by(
                PrimaryMarketRate.line_number.asc(), PrimaryMarketRate.rate_id.asc()
            )
        )
        .scalars()
        .all()
    )
    payload = build_xlsx(
        "taxas",
        [
            "rate_id",
            "mes",
            "indexador",
            "cnpj",
            "emissor",
            "taxa",
            "vencimento",
            "status",
            "observacao",
        ],
        [
            [
                row.rate_id,
                row.mes,
                row.indexador,
                row.cnpj,
                row.emissor,
                row.taxa,
                row.vencimento,
                row.status,
                row.observacao or "",
            ]
            for row in rows
        ],
        column_widths={1: 16, 2: 12, 3: 16, 4: 24, 5: 28, 6: 12, 7: 16, 8: 12, 9: 64},
    )
    filename = (
        file_record.nome_arquivo
        if file_record.nome_arquivo.endswith(".xlsx")
        else f"{file_record.nome_arquivo}.xlsx"
    )
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(payload)),
        },
    )


@router.get(
    f"{PREFIX}/files/{{file_id}}",
    response_model=IngestionFileResponse,
    tags=[TAG],
    operation_id="labs_group02_get_file",
    summary="Get one ingestion file by id",
    responses={404: {"description": "File not found"}, 422: _GROUP02_422},
)
async def get_file(
    file_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group02,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> IngestionFileResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return IngestionFileResponse.model_validate(_file_or_404(db, file_id))
