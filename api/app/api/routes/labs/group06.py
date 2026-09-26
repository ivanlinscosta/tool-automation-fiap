from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....labs.deps import LABS_GROUP_PATH, LabGroupHeader, Scenario, entity_not_found, require_group, scenario_or_422
from ....labs.generators import LAB_NOW
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group06_purchase import (
    Approval,
    ApprovalDecisionCreate,
    ApprovalResponse,
    Budget,
    BudgetCheckResponse,
    BudgetResponse,
    EmailRequest,
    EmailRequestCreate,
    EmailRequestResponse,
    Notification,
    NotificationResponse,
    PurchaseOrder,
    PurchaseOrderResponse,
    PurchaseOrderStatusResponse,
    PurchaseRequest,
    PurchaseRequestResponse,
    Vendor,
    VendorResponse,
    extract_purchase_data,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 06"
Group06 = Depends(require_group(6))

EMAIL_SORT_FIELDS = ("recebido_em", "request_id", "processado")
REQUEST_SORT_FIELDS = ("created_at", "updated_at", "status", "valor_estimado", "capexNumber")
PO_SORT_FIELDS = ("created_at", "updated_at", "status", "valor_total", "purchaseOrderNumber")
VENDOR_SORT_FIELDS = ("nome", "categoria", "prazo_entrega_dias")
BUDGET_SORT_FIELDS = ("capexNumber", "saldo", "valor_aprovado", "valor_comprometido")
APPROVAL_SORT_FIELDS = ("decided_at", "stage", "decisao")
NOTIFICATION_SORT_FIELDS = ("enviado_em", "canal", "lida")

_RESPONSES_422 = {
    "description": "Simulated validation error requested via ?scenario=validation_error",
    "content": {"application/json": {"example": {"detail": "Simulated validation error"}}},
}


def _email_or_404(db: Session, request_id: str) -> EmailRequest:
    email = db.get(EmailRequest, request_id)
    if email is None:
        raise entity_not_found("EmailRequest", request_id)
    return email


def _request_or_404(db: Session, request_id: str) -> PurchaseRequest:
    request = db.get(PurchaseRequest, request_id)
    if request is None:
        raise entity_not_found("PurchaseRequest", request_id)
    return request


def _budget_or_404(db: Session, capex_number: str) -> Budget:
    budget = db.get(Budget, capex_number)
    if budget is None:
        raise entity_not_found("Budget", capex_number)
    return budget


def _purchase_order_or_404(db: Session, purchase_order_number: str) -> PurchaseOrder:
    order = db.get(PurchaseOrder, purchase_order_number)
    if order is None:
        raise entity_not_found("PurchaseOrder", purchase_order_number)
    return order


def _next_email_id(db: Session) -> str:
    highest = db.execute(select(EmailRequest.request_id).order_by(EmailRequest.request_id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "EML-000001"
    return f"EML-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _next_request_id(db: Session) -> str:
    highest = db.execute(select(PurchaseRequest.id).order_by(PurchaseRequest.id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "PR-000001"
    return f"PR-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _next_po_id(db: Session) -> str:
    highest = db.execute(select(PurchaseOrder.purchaseOrderNumber).order_by(PurchaseOrder.purchaseOrderNumber.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "PO-000001"
    return f"PO-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _next_notification_id(db: Session) -> str:
    highest = db.execute(select(Notification.id).order_by(Notification.id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "NTF-000001"
    return f"NTF-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _next_approval_id(db: Session) -> str:
    count = db.execute(select(func.count()).select_from(Approval)).scalar_one()
    return f"APR-{count + 1:06d}"


def _find_vendor_by_name(db: Session, supplier_name: str) -> Vendor:
    vendor = db.execute(select(Vendor).where(func.lower(Vendor.nome) == supplier_name.lower())).scalar_one_or_none()
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Fornecedor '{supplier_name}' nao encontrado")
    return vendor


def _budget_check(request: PurchaseRequest, budget: Budget) -> BudgetCheckResponse:
    approved = budget.saldo >= request.valor_estimado
    missing = 0.0 if approved else round(request.valor_estimado - budget.saldo, 2)
    return BudgetCheckResponse(
        purchase_request_id=request.id,
        capexNumber=request.capexNumber,
        valor_estimado=request.valor_estimado,
        saldo=budget.saldo,
        approved=approved,
        missing_amount=missing,
    )


def _approval_history(db: Session, purchase_order_number: str) -> list[Approval]:
    query = select(Approval).where(Approval.purchaseOrderNumber == purchase_order_number).order_by(Approval.stage.asc(), Approval.decided_at.asc())
    return list(db.execute(query).scalars().all())


@router.get(
    f"{PREFIX}/email-requests",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group06_list_email_requests",
    summary="List purchase request e-mails",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_email_requests(
    scenario: Scenario = None,
    group: LabGroup = Group06,
    processado: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(EMAIL_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(EmailRequest)
    if processado is not None:
        query = query.where(EmailRequest.processado.is_(processado))
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(EmailRequest.assunto).like(pattern),
                func.lower(EmailRequest.corpo).like(pattern),
                func.lower(EmailRequest.remetente).like(pattern),
            )
        )
    query = apply_sort(query, EmailRequest, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: EmailRequestResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/email-requests/{{request_id}}",
    response_model=EmailRequestResponse,
    tags=[TAG],
    operation_id="labs_group06_get_email_request",
    summary="Get one purchase request e-mail",
    responses={404: {"description": "Email request not found"}, 422: _RESPONSES_422},
)
async def get_email_request(
    request_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> EmailRequestResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return EmailRequestResponse.model_validate(_email_or_404(db, request_id))


@router.post(
    f"{PREFIX}/email-requests",
    response_model=EmailRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group06_create_email_request",
    summary="Register a purchase request e-mail when the body contains extractable data",
    responses={422: _RESPONSES_422},
)
async def create_email_request(
    payload: EmailRequestCreate,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> EmailRequestResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if extract_purchase_data(payload.corpo) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O corpo do e-mail nao contem dados de compra extraiveis")
    email = EmailRequest(
        request_id=_next_email_id(db),
        remetente=payload.remetente,
        assunto=payload.assunto,
        corpo=payload.corpo,
        recebido_em=payload.recebido_em or LAB_NOW,
        processado=False,
        purchase_request_id=None,
    )
    db.add(email)
    db.commit()
    create_event(
        db,
        event_type="lab_group06_email_created",
        lab_group=x_lab_group,
        resource_type="lab_g06_email_request",
        resource_id=email.request_id,
        metadata={"group": "06"},
    )
    return EmailRequestResponse.model_validate(email)


@router.post(
    f"{PREFIX}/email-requests/{{request_id}}/extract",
    response_model=PurchaseRequestResponse,
    tags=[TAG],
    operation_id="labs_group06_extract_email_request",
    summary="Extract a purchase request from a purchase e-mail using deterministic parsing",
    responses={404: {"description": "Email request not found"}, 422: _RESPONSES_422},
)
async def extract_email_request(
    request_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PurchaseRequestResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    email = _email_or_404(db, request_id)
    if email.purchase_request_id:
        return PurchaseRequestResponse.model_validate(_request_or_404(db, email.purchase_request_id))
    extracted = extract_purchase_data(email.corpo)
    if extracted is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nao foi possivel extrair capex, fornecedor, itens e valor do e-mail")
    budget = _budget_or_404(db, str(extracted["capexNumber"]))
    vendor = _find_vendor_by_name(db, str(extracted["supplier_name"]))
    purchase_request = PurchaseRequest(
        id=_next_request_id(db),
        email_request_id=email.request_id,
        capexNumber=budget.capexNumber,
        supplierId=vendor.supplierId,
        descricao=str(extracted["descricao"]),
        valor_estimado=float(extracted["valor_estimado"]),
        status="RECEBIDO",
        created_at=LAB_NOW,
        updated_at=LAB_NOW,
    )
    email.processado = True
    email.purchase_request_id = purchase_request.id
    db.add(purchase_request)
    db.commit()
    create_event(
        db,
        event_type="lab_group06_email_extracted",
        lab_group=x_lab_group,
        resource_type="lab_g06_purchase_request",
        resource_id=purchase_request.id,
        metadata={"group": "06", "capexNumber": purchase_request.capexNumber},
    )
    return PurchaseRequestResponse.model_validate(purchase_request)


@router.get(
    f"{PREFIX}/purchase-requests",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group06_list_purchase_requests",
    summary="List extracted purchase requests",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_purchase_requests(
    scenario: Scenario = None,
    group: LabGroup = Group06,
    status_filter: str | None = Query(default=None, alias="status"),
    capexNumber: str | None = Query(default=None),
    supplierId: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(REQUEST_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(PurchaseRequest)
    if status_filter:
        query = query.where(PurchaseRequest.status == status_filter)
    if capexNumber:
        query = query.where(PurchaseRequest.capexNumber == capexNumber)
    if supplierId:
        query = query.where(PurchaseRequest.supplierId == supplierId)
    query = apply_sort(query, PurchaseRequest, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: PurchaseRequestResponse.model_validate(item).model_dump())


@router.post(
    f"{PREFIX}/purchase-requests/{{request_id}}/check-budget",
    response_model=BudgetCheckResponse,
    tags=[TAG],
    operation_id="labs_group06_check_budget",
    summary="Check whether the budget can fund the extracted purchase request",
    responses={404: {"description": "Purchase request or budget not found"}, 422: _RESPONSES_422},
)
async def check_budget(
    request_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> BudgetCheckResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    purchase_request = _request_or_404(db, request_id)
    budget = _budget_or_404(db, purchase_request.capexNumber)
    purchase_request.status = "EM_ANALISE"
    purchase_request.updated_at = LAB_NOW
    db.commit()
    create_event(
        db,
        event_type="lab_group06_budget_checked",
        lab_group=x_lab_group,
        resource_type="lab_g06_purchase_request",
        resource_id=purchase_request.id,
        metadata={"group": "06", "capexNumber": budget.capexNumber},
    )
    return _budget_check(purchase_request, budget)


@router.post(
    f"{PREFIX}/purchase-requests/{{request_id}}/purchase-order",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group06_create_purchase_order",
    summary="Create a purchase order when the budget has enough saldo",
    responses={404: {"description": "Purchase request or budget not found"}, 409: {"description": "Insufficient budget or duplicate purchase order"}, 422: _RESPONSES_422},
)
async def create_purchase_order(
    request_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    purchase_request = _request_or_404(db, request_id)
    existing = db.execute(select(PurchaseOrder).where(PurchaseOrder.request_id == purchase_request.id)).scalar_one_or_none()
    if existing is not None:
        return PurchaseOrderResponse.model_validate(existing)
    budget = _budget_or_404(db, purchase_request.capexNumber)
    if budget.saldo < purchase_request.valor_estimado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Saldo insuficiente para {purchase_request.capexNumber}: saldo={budget.saldo:.2f}, valor={purchase_request.valor_estimado:.2f}",
        )
    po = PurchaseOrder(
        purchaseOrderNumber=_next_po_id(db),
        request_id=purchase_request.id,
        capexNumber=purchase_request.capexNumber,
        supplierId=purchase_request.supplierId,
        valor_total=purchase_request.valor_estimado,
        status="RASCUNHO",
        created_at=LAB_NOW,
        updated_at=LAB_NOW,
    )
    budget.valor_comprometido = round(budget.valor_comprometido + po.valor_total, 2)
    budget.saldo = round(budget.valor_aprovado - budget.valor_comprometido, 2)
    purchase_request.status = "APROVADO"
    purchase_request.updated_at = LAB_NOW
    db.add(po)
    db.commit()
    create_event(
        db,
        event_type="lab_group06_purchase_order_created",
        lab_group=x_lab_group,
        resource_type="lab_g06_purchase_order",
        resource_id=po.purchaseOrderNumber,
        metadata={"group": "06", "capexNumber": po.capexNumber},
    )
    return PurchaseOrderResponse.model_validate(po)


@router.get(
    f"{PREFIX}/purchase-orders",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group06_list_purchase_orders",
    summary="List purchase orders",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_purchase_orders(
    scenario: Scenario = None,
    group: LabGroup = Group06,
    status_filter: str | None = Query(default=None, alias="status"),
    capexNumber: str | None = Query(default=None),
    supplierId: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(PO_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(PurchaseOrder)
    if status_filter:
        query = query.where(PurchaseOrder.status == status_filter)
    if capexNumber:
        query = query.where(PurchaseOrder.capexNumber == capexNumber)
    if supplierId:
        query = query.where(PurchaseOrder.supplierId == supplierId)
    query = apply_sort(query, PurchaseOrder, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: PurchaseOrderResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/purchase-orders/{{purchase_order_number}}",
    response_model=PurchaseOrderResponse,
    tags=[TAG],
    operation_id="labs_group06_get_purchase_order",
    summary="Get one purchase order by number",
    responses={404: {"description": "Purchase order not found"}, 422: _RESPONSES_422},
)
async def get_purchase_order(
    purchase_order_number: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return PurchaseOrderResponse.model_validate(_purchase_order_or_404(db, purchase_order_number))


@router.post(
    f"{PREFIX}/purchase-orders/{{purchase_order_number}}/submit",
    response_model=PurchaseOrderResponse,
    tags=[TAG],
    operation_id="labs_group06_submit_purchase_order",
    summary="Submit a draft purchase order to the approval workflow",
    responses={404: {"description": "Purchase order not found"}, 409: {"description": "Purchase order is not in draft status"}, 422: _RESPONSES_422},
)
async def submit_purchase_order(
    purchase_order_number: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    purchase_order = _purchase_order_or_404(db, purchase_order_number)
    if purchase_order.status != "RASCUNHO":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A purchase order so pode ser submetida a partir de RASCUNHO")
    purchase_order.status = "ENVIADA_APROVACAO"
    purchase_order.updated_at = LAB_NOW
    notification = Notification(
        id=_next_notification_id(db),
        destino=f"aprovacoes+{purchase_order.purchaseOrderNumber.lower()}@example.com",
        canal="email",
        mensagem=f"Purchase order {purchase_order.purchaseOrderNumber} enviada para aprovacao.",
        enviado_em=LAB_NOW,
        lida=False,
    )
    db.add(notification)
    db.commit()
    create_event(
        db,
        event_type="lab_group06_purchase_order_submitted",
        lab_group=x_lab_group,
        resource_type="lab_g06_purchase_order",
        resource_id=purchase_order.purchaseOrderNumber,
        metadata={"group": "06", "notification_id": notification.id},
    )
    return PurchaseOrderResponse.model_validate(purchase_order)


@router.post(
    f"{PREFIX}/purchase-orders/{{purchase_order_number}}/approve",
    response_model=PurchaseOrderStatusResponse,
    tags=[TAG],
    operation_id="labs_group06_approve_purchase_order",
    summary="Approve a purchase order stage by stage",
    responses={404: {"description": "Purchase order not found"}, 409: {"description": "Duplicate or out-of-order approval"}, 422: _RESPONSES_422},
)
async def approve_purchase_order(
    purchase_order_number: str,
    payload: ApprovalDecisionCreate,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PurchaseOrderStatusResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    if payload.stage not in (1, 2):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Este fluxo suporta apenas stage 1 e stage 2")
    purchase_order = _purchase_order_or_404(db, purchase_order_number)
    if purchase_order.status in {"REJEITADA", "APROVADA", "CONVERTIDA"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase order ja decidida")
    if purchase_order.status != "ENVIADA_APROVACAO":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase order ainda nao foi submetida para aprovacao")
    approvals = _approval_history(db, purchase_order_number)
    if any(item.stage == payload.stage for item in approvals):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Aprovacao duplicada para a mesma etapa")
    if payload.stage == 2 and not any(item.stage == 1 and item.decisao == "APROVADO" for item in approvals):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stage 2 nao pode ser aprovado antes do stage 1")
    approval = Approval(
        approval_id=_next_approval_id(db),
        purchaseOrderNumber=purchase_order_number,
        aprovador=payload.aprovador,
        decisao="APROVADO",
        comentario=payload.comentario,
        decided_at=LAB_NOW,
        stage=payload.stage,
    )
    if payload.stage == 2:
        purchase_order.status = "APROVADA"
    purchase_order.updated_at = LAB_NOW
    db.add(approval)
    db.commit()
    create_event(
        db,
        event_type="lab_group06_purchase_order_approved",
        lab_group=x_lab_group,
        resource_type="lab_g06_purchase_order",
        resource_id=purchase_order.purchaseOrderNumber,
        metadata={"group": "06", "stage": payload.stage},
    )
    approvals = _approval_history(db, purchase_order_number)
    return PurchaseOrderStatusResponse(
        purchase_order=PurchaseOrderResponse.model_validate(purchase_order),
        approvals=[ApprovalResponse.model_validate(item) for item in approvals],
        next_stage=None if purchase_order.status == "APROVADA" else 2,
        fully_approved=purchase_order.status == "APROVADA",
    )


@router.post(
    f"{PREFIX}/purchase-orders/{{purchase_order_number}}/reject",
    response_model=PurchaseOrderStatusResponse,
    tags=[TAG],
    operation_id="labs_group06_reject_purchase_order",
    summary="Reject a purchase order and release the committed budget",
    responses={404: {"description": "Purchase order not found"}, 409: {"description": "Duplicate decision or invalid workflow state"}, 422: _RESPONSES_422},
)
async def reject_purchase_order(
    purchase_order_number: str,
    payload: ApprovalDecisionCreate,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PurchaseOrderStatusResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    purchase_order = _purchase_order_or_404(db, purchase_order_number)
    if purchase_order.status in {"REJEITADA", "APROVADA", "CONVERTIDA"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase order ja decidida")
    if purchase_order.status != "ENVIADA_APROVACAO":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase order ainda nao foi submetida para aprovacao")
    approvals = _approval_history(db, purchase_order_number)
    if any(item.stage == payload.stage for item in approvals):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ja existe decisao para esta etapa")
    approval = Approval(
        approval_id=_next_approval_id(db),
        purchaseOrderNumber=purchase_order_number,
        aprovador=payload.aprovador,
        decisao="REJEITADO",
        comentario=payload.comentario,
        decided_at=LAB_NOW,
        stage=payload.stage,
    )
    budget = _budget_or_404(db, purchase_order.capexNumber)
    budget.valor_comprometido = round(max(0.0, budget.valor_comprometido - purchase_order.valor_total), 2)
    budget.saldo = round(budget.valor_aprovado - budget.valor_comprometido, 2)
    purchase_order.status = "REJEITADA"
    purchase_order.updated_at = LAB_NOW
    db.add(approval)
    db.commit()
    create_event(
        db,
        event_type="lab_group06_purchase_order_rejected",
        lab_group=x_lab_group,
        resource_type="lab_g06_purchase_order",
        resource_id=purchase_order.purchaseOrderNumber,
        metadata={"group": "06", "stage": payload.stage},
    )
    approvals = _approval_history(db, purchase_order_number)
    return PurchaseOrderStatusResponse(
        purchase_order=PurchaseOrderResponse.model_validate(purchase_order),
        approvals=[ApprovalResponse.model_validate(item) for item in approvals],
        next_stage=None,
        fully_approved=False,
    )


@router.get(
    f"{PREFIX}/purchase-orders/{{purchase_order_number}}/status",
    response_model=PurchaseOrderStatusResponse,
    tags=[TAG],
    operation_id="labs_group06_purchase_order_status",
    summary="Get a purchase order workflow summary",
    responses={404: {"description": "Purchase order not found"}, 422: _RESPONSES_422},
)
async def purchase_order_status(
    purchase_order_number: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> PurchaseOrderStatusResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    purchase_order = _purchase_order_or_404(db, purchase_order_number)
    approvals = _approval_history(db, purchase_order_number)
    next_stage = None
    if purchase_order.status == "ENVIADA_APROVACAO":
        next_stage = 1 if not approvals else 2
    return PurchaseOrderStatusResponse(
        purchase_order=PurchaseOrderResponse.model_validate(purchase_order),
        approvals=[ApprovalResponse.model_validate(item) for item in approvals],
        next_stage=next_stage,
        fully_approved=purchase_order.status == "APROVADA",
    )


@router.get(
    f"{PREFIX}/vendors",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group06_list_vendors",
    summary="List registered vendors",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_vendors(
    scenario: Scenario = None,
    group: LabGroup = Group06,
    categoria: str | None = Query(default=None),
    ativo: bool | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(VENDOR_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Vendor)
    if categoria:
        query = query.where(Vendor.categoria == categoria)
    if ativo is not None:
        query = query.where(Vendor.ativo.is_(ativo))
    query = apply_sort(query, Vendor, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: VendorResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/budgets",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group06_list_budgets",
    summary="List CAPEX budgets",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_budgets(
    scenario: Scenario = None,
    group: LabGroup = Group06,
    centro_custo: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(BUDGET_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Budget)
    if centro_custo:
        query = query.where(Budget.centro_custo == centro_custo)
    query = apply_sort(query, Budget, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: BudgetResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/budgets/{{capex_number}}",
    response_model=BudgetResponse,
    tags=[TAG],
    operation_id="labs_group06_get_budget",
    summary="Get one CAPEX budget including saldo and committed amount",
    responses={404: {"description": "Budget not found"}, 422: _RESPONSES_422},
)
async def get_budget(
    capex_number: str,
    scenario: Scenario = None,
    group: LabGroup = Group06,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> BudgetResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return BudgetResponse.model_validate(_budget_or_404(db, capex_number))


@router.get(
    f"{PREFIX}/approvals",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group06_list_approvals",
    summary="List approval decisions",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_approvals(
    scenario: Scenario = None,
    group: LabGroup = Group06,
    purchaseOrderNumber: str | None = Query(default=None),
    decisao: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(APPROVAL_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Approval)
    if purchaseOrderNumber:
        query = query.where(Approval.purchaseOrderNumber == purchaseOrderNumber)
    if decisao:
        query = query.where(Approval.decisao == decisao)
    query = apply_sort(query, Approval, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: ApprovalResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/notifications",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group06_list_notifications",
    summary="List approval workflow notifications",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_notifications(
    scenario: Scenario = None,
    group: LabGroup = Group06,
    canal: str | None = Query(default=None),
    lida: bool | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(NOTIFICATION_SORT_FIELDS)}."),
    order: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Notification)
    if canal:
        query = query.where(Notification.canal == canal)
    if lida is not None:
        query = query.where(Notification.lida.is_(lida))
    query = apply_sort(query, Notification, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: NotificationResponse.model_validate(item).model_dump())
