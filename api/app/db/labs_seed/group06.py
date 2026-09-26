import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group06 import build_email_body
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    LAB_TODAY,
    cnpj,
    company_name,
    email_address,
    group_rng,
    money,
    next_moment,
    previous_moment,
    weighted,
)
from ...models.labs.group06_purchase import (
    Approval,
    Budget,
    EmailRequest,
    Notification,
    PurchaseOrder,
    PurchaseRequest,
    Vendor,
)


logger = logging.getLogger(__name__)


def _already_seeded(db: Session) -> bool:
    return db.execute(select(func.count()).select_from(PurchaseOrder)).scalar_one() > 0


def seed_group(db: Session) -> None:
    if _already_seeded(db):
        logger.info("Group 06 already seeded")
        return

    rng = group_rng(6)

    vendors: list[Vendor] = []
    vendor_names: list[str] = []
    for index in range(90):
        nome = company_name(rng)
        vendor_names.append(nome)
        vendors.append(
            Vendor(
                supplierId=f"SUP-{index + 1:04d}",
                nome=nome,
                cnpj=cnpj(rng, valid=index % 8 != 0),
                categoria=("hardware", "software", "servicos", "infra", "seguranca")[index % 5],
                ativo=index % 13 != 0,
                prazo_entrega_dias=5 + index % 21,
            )
        )
    db.add_all(vendors)
    db.flush()

    budgets: list[Budget] = []
    for index in range(240):
        valor_aprovado = money(rng, 150000.0, 320000.0)
        budgets.append(
            Budget(
                capexNumber=f"CAPEX-{index + 1:04d}",
                centro_custo=f"CC-{200 + index:04d}",
                valor_aprovado=valor_aprovado,
                valor_comprometido=0.0,
                saldo=valor_aprovado,
                vigente_de=LAB_TODAY - timedelta(days=180 + index % 40),
                vigente_ate=LAB_TODAY + timedelta(days=120 + index % 50),
            )
        )
    db.add_all(budgets)
    db.flush()

    active_vendors = [vendor for vendor in vendors if vendor.ativo]
    budgets_by_capex = {budget.capexNumber: budget for budget in budgets}

    email_requests: list[EmailRequest] = []
    purchase_requests: list[PurchaseRequest] = []
    purchase_orders: list[PurchaseOrder] = []
    approvals: list[Approval] = []
    notifications: list[Notification] = []

    total = LAB_MIN_RECORDS + 120
    for index in range(total):
        budget = budgets[index % len(budgets)]
        vendor = active_vendors[index % len(active_vendors)]
        received_at = previous_moment(rng, LAB_NOW, min_minutes=5, max_days=220)
        request_created = next_moment(rng, received_at, min_minutes=5, max_days=2)
        request_updated = next_moment(rng, request_created, min_minutes=15, max_days=4)
        item_text = f"{1 + index % 6} notebooks corporativos e {2 + index % 4} monitores"
        valor_total = money(rng, 3500.0, 18500.0)
        status = weighted(
            rng,
            [
                ("RASCUNHO", 18),
                ("ENVIADA_APROVACAO", 26),
                ("APROVADA", 28),
                ("REJEITADA", 12),
                ("CONVERTIDA", 16),
            ],
        )
        supplier_text = vendor.nome
        body = build_email_body(
            rng,
            capex=budget.capexNumber,
            supplier=supplier_text,
            items=item_text,
            total=f"{valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            days=vendor.prazo_entrega_dias,
        )
        email = EmailRequest(
            request_id=f"EML-{index + 1:06d}",
            remetente=email_address(rng),
            assunto=f"Solicitacao de compra {budget.capexNumber}",
            corpo=body,
            recebido_em=received_at,
            processado=True,
            purchase_request_id=f"PR-{index + 1:06d}",
        )
        email_requests.append(email)

        pr_status = "REJEITADO" if status == "REJEITADA" else ("APROVADO" if status in {"APROVADA", "CONVERTIDA"} else "EM_ANALISE")
        purchase_request = PurchaseRequest(
            id=f"PR-{index + 1:06d}",
            email_request_id=email.request_id,
            capexNumber=budget.capexNumber,
            supplierId=vendor.supplierId,
            descricao=item_text,
            valor_estimado=valor_total,
            status=pr_status,
            created_at=request_created,
            updated_at=request_updated,
        )
        purchase_requests.append(purchase_request)

        po_created = next_moment(rng, request_created, min_minutes=20, max_days=3)
        po_updated = next_moment(rng, po_created, min_minutes=20, max_days=6)
        po = PurchaseOrder(
            purchaseOrderNumber=f"PO-{index + 1:06d}",
            request_id=purchase_request.id,
            capexNumber=budget.capexNumber,
            supplierId=vendor.supplierId,
            valor_total=valor_total,
            status=status,
            created_at=po_created,
            updated_at=po_updated,
        )
        purchase_orders.append(po)

        if status != "REJEITADA":
            budget.valor_comprometido = round(budget.valor_comprometido + valor_total, 2)
            budget.saldo = round(budget.valor_aprovado - budget.valor_comprometido, 2)

        if status in {"ENVIADA_APROVACAO", "APROVADA", "CONVERTIDA", "REJEITADA"}:
            notify_at = next_moment(rng, po_created, min_minutes=10, max_days=2)
            notifications.append(
                Notification(
                    id=f"NTF-{index + 1:06d}",
                    destino=f"aprovador.{(index % 12) + 1:02d}@example.com",
                    canal=("email", "slack")[index % 2],
                    mensagem=f"PO {po.purchaseOrderNumber} enviada para aprovacao.",
                    enviado_em=notify_at,
                    lida=index % 5 == 0,
                )
            )

        if status in {"APROVADA", "CONVERTIDA"}:
            first_at = next_moment(rng, po_created, min_minutes=30, max_days=2)
            second_at = next_moment(rng, first_at, min_minutes=30, max_days=2)
            approvals.append(
                Approval(
                    approval_id=f"APR-{index + 1:06d}-1",
                    purchaseOrderNumber=po.purchaseOrderNumber,
                    aprovador=f"gerente.{(index % 10) + 1:02d}",
                    decisao="APROVADO",
                    comentario="Primeira aprovacao concluida.",
                    decided_at=first_at,
                    stage=1,
                )
            )
            approvals.append(
                Approval(
                    approval_id=f"APR-{index + 1:06d}-2",
                    purchaseOrderNumber=po.purchaseOrderNumber,
                    aprovador=f"diretor.{(index % 6) + 1:02d}",
                    decisao="APROVADO",
                    comentario="Segunda aprovacao concluida.",
                    decided_at=second_at,
                    stage=2,
                )
            )
        elif status == "ENVIADA_APROVACAO":
            if index % 2 == 0:
                first_at = next_moment(rng, po_created, min_minutes=30, max_days=2)
                approvals.append(
                    Approval(
                        approval_id=f"APR-{index + 1:06d}-1",
                        purchaseOrderNumber=po.purchaseOrderNumber,
                        aprovador=f"gerente.{(index % 10) + 1:02d}",
                        decisao="APROVADO",
                        comentario="Primeira etapa aprovada.",
                        decided_at=first_at,
                        stage=1,
                    )
                )
        elif status == "REJEITADA":
            reject_at = next_moment(rng, po_created, min_minutes=30, max_days=2)
            approvals.append(
                Approval(
                    approval_id=f"APR-{index + 1:06d}-R",
                    purchaseOrderNumber=po.purchaseOrderNumber,
                    aprovador=f"gerente.{(index % 10) + 1:02d}",
                    decisao="REJEITADO",
                    comentario="Fornecedor fora da politica.",
                    decided_at=reject_at,
                    stage=1,
                )
            )

    for budget in budgets_by_capex.values():
        if budget.saldo < 5000:
            budget.saldo = 5000.0
            budget.valor_comprometido = round(budget.valor_aprovado - budget.saldo, 2)

    db.add_all(email_requests)
    db.add_all(purchase_requests)
    db.add_all(purchase_orders)
    db.add_all(approvals)
    db.add_all(notifications)
    db.commit()
    logger.info("Group 06 seeded with %d purchase orders", len(purchase_orders))
