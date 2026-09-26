import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group05 import build_message
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    cpf,
    email_address,
    group_rng,
    is_valid_cpf,
    money,
    next_moment,
    person_name,
    previous_moment,
    brazilian_phone,
    weighted,
)
from ...models.labs.group05_pos_venda import (
    Customer,
    Message,
    Order,
    ResponseTemplate,
    Shipment,
    Ticket,
    ticket_priority_for,
)


logger = logging.getLogger(__name__)


def _already_seeded(db: Session) -> bool:
    return db.execute(select(func.count()).select_from(Ticket)).scalar_one() > 0


def seed_group(db: Session) -> None:
    if _already_seeded(db):
        logger.info("Group 05 already seeded")
        return

    rng = group_rng(5)

    templates = [
        ResponseTemplate(template_id="TPL-0001", intencao="troca_produto", texto="Recebemos sua solicitacao de troca e vamos orientar o passo a passo.", ativo=True),
        ResponseTemplate(template_id="TPL-0002", intencao="defeito_produto", texto="Lamentamos o ocorrido. Vamos registrar a analise do produto com defeito.", ativo=True),
        ResponseTemplate(template_id="TPL-0003", intencao="rastreio_pedido", texto="Estamos consultando a transportadora e retornaremos com a atualizacao do rastreio.", ativo=True),
        ResponseTemplate(template_id="TPL-0004", intencao="fatura_segunda_via", texto="Segue o fluxo para emissao da segunda via da fatura e do boleto.", ativo=True),
        ResponseTemplate(template_id="TPL-0005", intencao="reclamacao_atraso", texto="Acionamos a logistica e priorizamos a tratativa do atraso informado.", ativo=True),
        ResponseTemplate(template_id="TPL-0006", intencao="duvida_uso", texto="Vamos apoiar o uso do produto com orientacoes claras e objetivas.", ativo=True),
        ResponseTemplate(template_id="TPL-0091", intencao="troca_produto", texto="Template historico desativado para troca.", ativo=False),
        ResponseTemplate(template_id="TPL-0092", intencao="reclamacao_atraso", texto="Template historico desativado para atraso.", ativo=False),
    ]
    db.add_all(templates)

    customers: list[Customer] = []
    for index in range(720):
        created_at = previous_moment(rng, LAB_NOW, min_minutes=10, max_days=500)
        updated_at = next_moment(rng, created_at, min_minutes=5, max_days=90)
        customer_cpf = None
        if index % 9 != 0:
            customer_cpf = cpf(rng, valid=index % 11 != 0)
        customer_phone = None if index % 10 == 0 else brazilian_phone(rng)
        customer = Customer(
            customer_id=f"CUS-PV-{index + 1:05d}",
            nome=person_name(rng),
            cpf=customer_cpf,
            telefone=customer_phone,
            email=email_address(rng),
            created_at=created_at,
            updated_at=updated_at,
        )
        customers.append(customer)
    db.add_all(customers)
    db.flush()

    orders: list[Order] = []
    for index in range(980):
        customer = customers[index % len(customers)]
        created_at = previous_moment(rng, LAB_NOW, min_minutes=20, max_days=320)
        status = weighted(
            rng,
            [
                ("confirmado", 16),
                ("separado", 18),
                ("enviado", 22),
                ("entregue", 34),
                ("cancelado", 10),
            ],
        )
        updated_at = next_moment(rng, created_at, min_minutes=15, max_days=20)
        orders.append(
            Order(
                order_id=f"PV-{index + 1:06d}",
                customer_id=customer.customer_id,
                valor_total=money(rng, 89.0, 2899.0),
                data_pedido=created_at,
                status=status,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
    db.add_all(orders)
    db.flush()

    shipments: list[Shipment] = []
    for index, order in enumerate(orders, start=1):
        if order.status == "cancelado":
            continue
        data_envio = next_moment(rng, order.data_pedido, min_minutes=60, max_days=6)
        status = "entregue" if order.status == "entregue" else rng.choice(("coletado", "em_transito", "extraviado", "em_transito"))
        days_until_due = 2 + index % 8
        prevista = min(LAB_NOW.date(), data_envio.date() + timedelta(days=days_until_due))
        data_entrega_real = None
        if status == "entregue":
            extra_days = -1 if index % 6 == 0 else index % 4
            candidate = data_envio + timedelta(days=max(0, days_until_due + extra_days), hours=index % 13)
            data_entrega_real = min(candidate, LAB_NOW)
        shipment_updated = data_entrega_real or next_moment(rng, data_envio, min_minutes=15, max_days=8)
        shipments.append(
            Shipment(
                shipment_id=f"SHP-PV-{index:06d}",
                order_id=order.order_id,
                codigo_rastreio=f"BRPV{index:010d}",
                transportadora=("Correio Sul", "Entrega Agora", "Rapido Express", "Carga Certa")[index % 4],
                status=status,
                data_envio=data_envio,
                data_entrega_prevista=prevista,
                data_entrega_real=data_entrega_real,
                created_at=data_envio,
                updated_at=shipment_updated,
            )
        )
    db.add_all(shipments)
    db.flush()

    active_templates = {template.intencao: template.template_id for template in templates if template.ativo}
    customers_by_id = {customer.customer_id: customer for customer in customers}

    messages: list[Message] = []
    tickets: list[Ticket] = []
    total_tickets = LAB_MIN_RECORDS + 140
    intention_weights = [
        ("troca_produto", 18),
        ("defeito_produto", 15),
        ("rastreio_pedido", 24),
        ("fatura_segunda_via", 10),
        ("reclamacao_atraso", 18),
        ("duvida_uso", 15),
    ]

    for index in range(total_tickets):
        intencao = weighted(rng, intention_weights)
        linked_order = None if index % 7 == 0 else orders[index % len(orders)]
        linked_customer = customers_by_id[linked_order.customer_id] if linked_order is not None else customers[index % len(customers)]
        message_created = previous_moment(rng, LAB_NOW, min_minutes=5, max_days=180)
        message_updated = next_moment(rng, message_created, min_minutes=5, max_days=4)

        customer_name = linked_customer.nome if index % 13 != 0 else None
        cpf_informado = linked_customer.cpf if linked_order is not None and index % 5 != 0 else None
        telefone_informado = linked_customer.telefone if index % 4 != 0 else None
        if linked_order is None and index % 3 == 0:
            cpf_informado = None
            telefone_informado = None

        message = Message(
            message_id=f"MSG-PV-{index + 1:06d}",
            customer_name=customer_name,
            cpf_informado=cpf_informado,
            telefone_informado=telefone_informado,
            email_informado=linked_customer.email if index % 6 != 0 else None,
            texto=build_message(rng, intencao),
            customer_id=linked_customer.customer_id if linked_order is not None else None,
            order_id=linked_order.order_id if linked_order is not None else None,
            intencao=intencao,
            created_at=message_created,
            updated_at=message_updated,
        )
        messages.append(message)

        prioridade, sla_horas = ticket_priority_for(intencao, has_order=linked_order is not None)
        status = "RESPONDIDO" if index % 6 == 0 else "ABERTO"
        if linked_order is None:
            status = "AGUARDANDO_IDENTIFICACAO" if index % 2 == 0 else "ABERTO"
        responded_at = next_moment(rng, message_created, min_minutes=30, max_days=3) if status == "RESPONDIDO" else None
        response_text = templates[(index % 6)].texto if responded_at else None
        if linked_customer.cpf and not is_valid_cpf(linked_customer.cpf) and intencao == "fatura_segunda_via":
            prioridade = "alta"
            sla_horas = 8
        tickets.append(
            Ticket(
                ticket_id=f"TCK-PV-{index + 1:06d}",
                message_id=message.message_id,
                order_id=linked_order.order_id if linked_order is not None else None,
                customer_id=linked_customer.customer_id if linked_order is not None else None,
                prioridade=prioridade,
                sla_horas=sla_horas,
                resposta_template_id=active_templates[intencao],
                status=status,
                response_text=response_text,
                responded_at=responded_at,
                created_at=message_created,
                updated_at=responded_at or message_updated,
            )
        )

    db.add_all(messages)
    db.add_all(tickets)
    db.commit()
    logger.info("Group 05 seeded with %d tickets", len(tickets))
