
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
from ....labs.normalize import normalize_phone
from ....labs.pagination import apply_sort, build_page
from ....labs.registry import LabGroup
from ....labs.scenarios import apply_scenario
from ....models.labs.group05_pos_venda import (
    Customer,
    CustomerResponse,
    Group05StatsResponse,
    Message,
    MessageCreate,
    MessageCreateResponse,
    MessageInstructorResponse,
    MessageResponse,
    MessageTriage,
    Order,
    OrderResponse,
    ResponseTemplate,
    ResponseTemplateResponse,
    Shipment,
    ShipmentResponse,
    Ticket,
    TicketRespond,
    TicketResponse,
    ticket_priority_for,
)
from ....services.audit_service import create_event


router = APIRouter()

PREFIX = LABS_GROUP_PATH
TAG = "Lab - Group 05"
Group05 = Depends(require_group(5))

MESSAGE_SORT_FIELDS = ("created_at", "updated_at", "customer_name", "order_id")
TICKET_SORT_FIELDS = ("created_at", "updated_at", "prioridade", "status", "sla_horas")
ORDER_SORT_FIELDS = ("data_pedido", "valor_total", "status", "created_at")
SHIPMENT_SORT_FIELDS = ("data_envio", "status", "transportadora", "updated_at")
CUSTOMER_SORT_FIELDS = ("nome", "created_at", "updated_at")
TEMPLATE_SORT_FIELDS = ("template_id", "intencao")

_RESPONSES_422 = {
    "description": "Simulated validation error requested via ?scenario=validation_error",
    "content": {"application/json": {"example": {"detail": "Simulated validation error"}}},
}


def _message_or_404(db: Session, message_id: str) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise entity_not_found("Message", message_id)
    return message


def _ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise entity_not_found("Ticket", ticket_id)
    return ticket


def _order_or_404(db: Session, order_id: str) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise entity_not_found("Order", order_id)
    return order


def _customer_or_404(db: Session, customer_id: str) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise entity_not_found("Customer", customer_id)
    return customer


def _template_or_404(db: Session, template_id: str) -> ResponseTemplate:
    template = db.get(ResponseTemplate, template_id)
    if template is None:
        raise entity_not_found("ResponseTemplate", template_id)
    return template


def _next_message_id(db: Session) -> str:
    highest = db.execute(select(Message.message_id).order_by(Message.message_id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "MSG-PV-000001"
    return f"MSG-PV-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _next_ticket_id(db: Session) -> str:
    highest = db.execute(select(Ticket.ticket_id).order_by(Ticket.ticket_id.desc()).limit(1)).scalar_one_or_none()
    if highest is None:
        return "TCK-PV-000001"
    return f"TCK-PV-{int(highest.rsplit('-', maxsplit=1)[1]) + 1:06d}"


def _resolve_latest_order_for_customer(db: Session, customer: Customer) -> Order | None:
    query = (
        select(Order)
        .where(Order.customer_id == customer.customer_id)
        .order_by(Order.data_pedido.desc(), Order.order_id.desc())
        .limit(1)
    )
    return db.execute(query).scalar_one_or_none()


def _resolve_customer_and_order(
    db: Session,
    *,
    cpf: str | None,
    telefone: str | None,
    order_id: str | None,
) -> tuple[Customer | None, Order | None]:
    if order_id:
        order = _order_or_404(db, order_id)
        return _customer_or_404(db, order.customer_id), order
    if cpf:
        if not is_valid_cpf(cpf):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CPF invalido")
        customer = db.execute(select(Customer).where(Customer.cpf == cpf)).scalar_one_or_none()
        if customer is None:
            raise entity_not_found("Customer", cpf)
        order = _resolve_latest_order_for_customer(db, customer)
        if order is None:
            raise entity_not_found("Order", customer.customer_id)
        return customer, order
    if telefone:
        normalized = normalize_phone(telefone)
        customer = None
        for candidate in db.execute(select(Customer).where(Customer.telefone.is_not(None))).scalars().all():
            if normalize_phone(candidate.telefone) == normalized:
                customer = candidate
                break
        if customer is None:
            raise entity_not_found("Customer", telefone)
        order = _resolve_latest_order_for_customer(db, customer)
        if order is None:
            raise entity_not_found("Order", customer.customer_id)
        return customer, order
    return None, None


def _active_template_for_intent(db: Session, intencao: str) -> ResponseTemplate:
    template = db.execute(
        select(ResponseTemplate)
        .where(ResponseTemplate.intencao == intencao, ResponseTemplate.ativo.is_(True))
        .order_by(ResponseTemplate.template_id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No active template available for '{intencao}'")
    return template


@router.get(
    f"{PREFIX}/messages",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_list_messages",
    summary="List post-sale messages with filters, sorting and pagination",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_messages(
    scenario: Scenario = None,
    group: LabGroup = Group05,
    intencao: str | None = Query(default=None, description="Optional intention filter used for instructor exercises."),
    com_pedido: bool | None = Query(default=None, description="Filter messages already linked to an order."),
    search: str | None = Query(default=None, description="Case-insensitive search on customer data, order id and message text."),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(MESSAGE_SORT_FIELDS)}."),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Message)
    if intencao:
        query = query.where(Message.intencao == intencao)
    if com_pedido is True:
        query = query.where(Message.order_id.is_not(None))
    if com_pedido is False:
        query = query.where(Message.order_id.is_(None))
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(func.coalesce(Message.customer_name, "")).like(pattern),
                func.lower(func.coalesce(Message.texto, "")).like(pattern),
                func.lower(func.coalesce(Message.order_id, "")).like(pattern),
                func.lower(func.coalesce(Message.cpf_informado, "")).like(pattern),
                func.lower(func.coalesce(Message.telefone_informado, "")).like(pattern),
            )
        )
    query = apply_sort(query, Message, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: MessageResponse.model_validate(item).model_dump())


@router.post(
    f"{PREFIX}/messages",
    response_model=MessageCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=[TAG],
    operation_id="labs_group05_create_message",
    summary="Register an incoming post-sale message",
    responses={422: _RESPONSES_422},
)
async def create_message(
    payload: MessageCreate,
    scenario: Scenario = None,
    group: LabGroup = Group05,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> MessageCreateResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    message = Message(
        message_id=_next_message_id(db),
        customer_name=payload.customer_name,
        cpf_informado=payload.cpf,
        telefone_informado=payload.telefone,
        email_informado=payload.email,
        texto=payload.texto,
        customer_id=None,
        order_id=None,
        intencao=None,
        created_at=LAB_NOW,
        updated_at=LAB_NOW,
    )
    db.add(message)
    db.commit()
    create_event(
        db,
        event_type="lab_group05_message_created",
        lab_group=x_lab_group,
        resource_type="lab_g05_message",
        resource_id=message.message_id,
        metadata={"group": "05"},
    )
    return MessageCreateResponse.model_validate(message)


@router.post(
    f"{PREFIX}/messages/{{message_id}}/triage",
    response_model=TicketResponse,
    tags=[TAG],
    operation_id="labs_group05_triage_message",
    summary="Classify a message, assign priority and link an order when identification is available",
    responses={404: {"description": "Message, customer or order not found"}, 422: _RESPONSES_422},
)
async def triage_message(
    message_id: str,
    payload: MessageTriage,
    scenario: Scenario = None,
    group: LabGroup = Group05,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> TicketResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    message = _message_or_404(db, message_id)
    customer, linked_order = _resolve_customer_and_order(db, cpf=payload.cpf, telefone=payload.telefone, order_id=payload.order_id)
    template = _active_template_for_intent(db, payload.intencao)
    prioridade, sla_horas = ticket_priority_for(payload.intencao, has_order=linked_order is not None or message.order_id is not None)

    message.intencao = payload.intencao
    if customer is not None:
        message.customer_id = customer.customer_id
    if linked_order is not None:
        message.order_id = linked_order.order_id
    message.updated_at = LAB_NOW

    ticket = db.execute(select(Ticket).where(Ticket.message_id == message.message_id)).scalar_one_or_none()
    if ticket is None:
        ticket = Ticket(
            ticket_id=_next_ticket_id(db),
            message_id=message.message_id,
            order_id=message.order_id,
            customer_id=message.customer_id,
            prioridade=prioridade,
            sla_horas=sla_horas,
            resposta_template_id=template.template_id,
            status="ABERTO" if message.order_id else "AGUARDANDO_IDENTIFICACAO",
            response_text=None,
            responded_at=None,
            created_at=LAB_NOW,
            updated_at=LAB_NOW,
        )
        db.add(ticket)
    else:
        ticket.order_id = message.order_id
        ticket.customer_id = message.customer_id
        ticket.prioridade = prioridade
        ticket.sla_horas = sla_horas
        ticket.resposta_template_id = template.template_id
        ticket.status = "ABERTO" if message.order_id else "AGUARDANDO_IDENTIFICACAO"
        ticket.updated_at = LAB_NOW

    db.commit()
    create_event(
        db,
        event_type="lab_group05_message_triaged",
        lab_group=x_lab_group,
        resource_type="lab_g05_ticket",
        resource_id=ticket.ticket_id,
        metadata={"group": "05", "intencao": payload.intencao, "template_id": template.template_id},
    )
    return TicketResponse.model_validate(ticket)


@router.get(
    f"{PREFIX}/orders/search",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_search_orders",
    summary="Search orders by CPF or phone",
    responses={404: {"description": "Customer or order not found"}, 422: _RESPONSES_422},
)
async def search_orders(
    scenario: Scenario = None,
    group: LabGroup = Group05,
    cpf: str | None = Query(default=None, description="Customer CPF used for lookup."),
    telefone: str | None = Query(default=None, description="Customer phone used for lookup when CPF is missing."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    if bool(cpf) == bool(telefone):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Informe exatamente um dos parametros: cpf ou telefone")
    customer, _ = _resolve_customer_and_order(db, cpf=cpf, telefone=telefone, order_id=None)
    if customer is None:
        raise entity_not_found("Customer", cpf or telefone or "")
    query = select(Order).where(Order.customer_id == customer.customer_id).order_by(Order.data_pedido.desc(), Order.order_id.desc())
    if db.execute(select(func.count()).select_from(query.subquery())).scalar_one() == 0:
        raise entity_not_found("Order", customer.customer_id)
    return build_page(db, query, limit, offset, serializer=lambda item: OrderResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/tickets",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_list_tickets",
    summary="List post-sale tickets",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_tickets(
    scenario: Scenario = None,
    group: LabGroup = Group05,
    prioridade: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(TICKET_SORT_FIELDS)}."),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Ticket)
    if prioridade:
        query = query.where(Ticket.prioridade == prioridade)
    if status_filter:
        query = query.where(Ticket.status == status_filter)
    query = apply_sort(query, Ticket, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: TicketResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/tickets/{{ticket_id}}",
    response_model=TicketResponse,
    tags=[TAG],
    operation_id="labs_group05_get_ticket",
    summary="Get one ticket by id",
    responses={404: {"description": "Ticket not found"}, 422: _RESPONSES_422},
)
async def get_ticket(
    ticket_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group05,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> TicketResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return TicketResponse.model_validate(_ticket_or_404(db, ticket_id))


@router.post(
    f"{PREFIX}/tickets/{{ticket_id}}/respond",
    response_model=TicketResponse,
    tags=[TAG],
    operation_id="labs_group05_respond_ticket",
    summary="Respond to a ticket using a template with idempotency by ticket and template",
    responses={404: {"description": "Ticket or template not found"}, 409: {"description": "Ticket already responded with another template"}, 422: _RESPONSES_422},
)
async def respond_ticket(
    ticket_id: str,
    payload: TicketRespond,
    scenario: Scenario = None,
    group: LabGroup = Group05,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> TicketResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = group
    ticket = _ticket_or_404(db, ticket_id)
    template = _template_or_404(db, payload.template_id)
    if ticket.responded_at is not None:
        if ticket.resposta_template_id == payload.template_id:
            return TicketResponse.model_validate(ticket)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ticket already responded with a different template")
    response_text = template.texto if not payload.resposta_manual else f"{template.texto} {payload.resposta_manual}".strip()
    ticket.resposta_template_id = template.template_id
    ticket.response_text = response_text
    ticket.status = "RESPONDIDO"
    ticket.responded_at = LAB_NOW
    ticket.updated_at = LAB_NOW
    db.commit()
    create_event(
        db,
        event_type="lab_group05_ticket_responded",
        lab_group=x_lab_group,
        resource_type="lab_g05_ticket",
        resource_id=ticket.ticket_id,
        metadata={"group": "05", "template_id": template.template_id},
    )
    return TicketResponse.model_validate(ticket)


@router.get(
    f"{PREFIX}/orders",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_list_orders",
    summary="List e-commerce orders",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_orders(
    scenario: Scenario = None,
    group: LabGroup = Group05,
    customer_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(ORDER_SORT_FIELDS)}."),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Order)
    if customer_id:
        query = query.where(Order.customer_id == customer_id)
    if status_filter:
        query = query.where(Order.status == status_filter)
    query = apply_sort(query, Order, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: OrderResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/orders/{{order_id}}",
    response_model=OrderResponse,
    tags=[TAG],
    operation_id="labs_group05_get_order",
    summary="Get one order by id",
    responses={404: {"description": "Order not found"}, 422: _RESPONSES_422},
)
async def get_order(
    order_id: str,
    scenario: Scenario = None,
    group: LabGroup = Group05,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> OrderResponse:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    return OrderResponse.model_validate(_order_or_404(db, order_id))


@router.get(
    f"{PREFIX}/shipments",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_list_shipments",
    summary="List shipment records",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_shipments(
    scenario: Scenario = None,
    group: LabGroup = Group05,
    status_filter: str | None = Query(default=None, alias="status"),
    order_id: str | None = Query(default=None),
    transportadora: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(SHIPMENT_SORT_FIELDS)}."),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Shipment)
    if status_filter:
        query = query.where(Shipment.status == status_filter)
    if order_id:
        query = query.where(Shipment.order_id == order_id)
    if transportadora:
        query = query.where(Shipment.transportadora == transportadora)
    query = apply_sort(query, Shipment, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: ShipmentResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/customers",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_list_customers",
    summary="List customers involved in post-sale messages and orders",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_customers(
    scenario: Scenario = None,
    group: LabGroup = Group05,
    cpf: str | None = Query(default=None),
    telefone: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(CUSTOMER_SORT_FIELDS)}."),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(Customer)
    if cpf:
        query = query.where(Customer.cpf == cpf)
    if telefone:
        query = query.where(Customer.telefone == telefone)
    if search:
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Customer.nome).like(pattern),
                func.lower(func.coalesce(Customer.email, "")).like(pattern),
                func.lower(func.coalesce(Customer.cpf, "")).like(pattern),
            )
        )
    query = apply_sort(query, Customer, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: CustomerResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/response-templates",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_list_response_templates",
    summary="List response templates available for the triage workflow",
    responses={400: {"description": "Invalid sort field"}, 422: _RESPONSES_422},
)
async def list_response_templates(
    scenario: Scenario = None,
    group: LabGroup = Group05,
    intencao: str | None = Query(default=None),
    ativo: bool | None = Query(default=None),
    sort: str | None = Query(default=None, description=f"One of: {', '.join(TEMPLATE_SORT_FIELDS)}."),
    order: str | None = Query(default=None, description="asc or desc."),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> dict:
    await apply_scenario(scenario_or_422(scenario))
    _ = (group, x_lab_group)
    query = select(ResponseTemplate)
    if intencao:
        query = query.where(ResponseTemplate.intencao == intencao)
    if ativo is not None:
        query = query.where(ResponseTemplate.ativo.is_(ativo))
    query = apply_sort(query, ResponseTemplate, sort, order)
    return build_page(db, query, limit, offset, serializer=lambda item: ResponseTemplateResponse.model_validate(item).model_dump())


@router.get(
    f"{PREFIX}/stats",
    response_model=dict,
    tags=[TAG],
    operation_id="labs_group05_stats",
    summary="Aggregate post-sale metrics by intention, priority and ticket status",
    responses={422: _RESPONSES_422},
)
async def group05_stats(
    group_id: str,
    scenario: Scenario = None,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> Group05StatsResponse | dict:
    await apply_scenario(scenario_or_422(scenario))
    from ....api.routes.labs import group08 as group08_module
    from ....labs.deps import lab_group

    resolved = lab_group(group_id, db)
    if resolved.group_id == 8:
        return (await group08_module.unlock_stats(
            scenario=None,
            group=resolved,
            x_lab_group=x_lab_group,
            db=db,
        )).model_dump()
    if resolved.group_id != 5:
        raise HTTPException(status_code=404, detail="Endpoint does not belong to lab group 05 or 08")

    _ = x_lab_group
    messages_by_intencao = {
        key: value
        for key, value in db.execute(select(Message.intencao, func.count()).group_by(Message.intencao)).all()
        if key is not None
    }
    tickets_by_prioridade = {key: value for key, value in db.execute(select(Ticket.prioridade, func.count()).group_by(Ticket.prioridade)).all()}
    tickets_by_status = {key: value for key, value in db.execute(select(Ticket.status, func.count()).group_by(Ticket.status)).all()}
    return Group05StatsResponse(
        messages_by_intencao=messages_by_intencao,
        tickets_by_prioridade=tickets_by_prioridade,
        tickets_by_status=tickets_by_status,
    ).model_dump()


@router.get(
    f"{PREFIX}/instructor/messages/{{message_id}}",
    response_model=MessageInstructorResponse,
    tags=[TAG],
    operation_id="labs_group05_instructor_get_message",
    summary="Instructor only: get one message including its hidden intention label",
    responses={401: {"description": "Missing or invalid X-Instructor-Key"}, 403: {"description": "Instructor endpoints disabled on this environment"}, 404: {"description": "Message not found"}, 422: _RESPONSES_422},
)
async def instructor_get_message(
    message_id: str,
    scenario: Scenario = None,
    instructor_key: InstructorKey = None,
    group: LabGroup = Group05,
    x_lab_group: LabGroupHeader = "anonymous",
    db: Session = Depends(get_db),
) -> MessageInstructorResponse:
    await apply_scenario(scenario_or_422(scenario))
    require_instructor_key(instructor_key)
    _ = (group, x_lab_group)
    return MessageInstructorResponse.model_validate(_message_or_404(db, message_id))
