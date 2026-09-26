import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group08 import build_unlock_reason
from ...labs.generators import LAB_MIN_RECORDS, LAB_NOW, LAB_TODAY, group_rng, money, next_moment, person_name, previous_moment
from ...models.labs.group08_unlock import (
    CreditCheck,
    CustomerContract,
    Invoice,
    UnlockDecision,
    UnlockHistory,
    UnlockRequest,
    expected_unlock_decision,
)


logger = logging.getLogger(__name__)


def _already_seeded(db: Session) -> bool:
    return db.execute(select(func.count()).select_from(UnlockRequest)).scalar_one() > 0


def seed_group(db: Session) -> None:
    if _already_seeded(db):
        logger.info("Group 08 already seeded")
        return

    rng = group_rng(8)

    contracts: list[CustomerContract] = []
    for index in range(760):
        status = ("ATIVO", "SUSPENSO", "ATIVO", "ATIVO", "CANCELADO")[index % 5]
        pending_invoices = index % 7
        start_date = LAB_TODAY - timedelta(days=400 + index % 200)
        end_date = None if status != "CANCELADO" else LAB_TODAY - timedelta(days=10 + index % 90)
        contracts.append(
            CustomerContract(
                customer_id=f"UC-{index + 1:06d}",
                customer_name=person_name(rng),
                contract_status=status,
                data_inicio=start_date,
                data_fim=end_date,
                monthly_value=money(rng, 99.0, 2200.0),
                pending_invoices=pending_invoices,
            )
        )
    db.add_all(contracts)
    db.flush()

    invoices: list[Invoice] = []
    credit_checks: list[CreditCheck] = []
    requests: list[UnlockRequest] = []
    histories: list[UnlockHistory] = []
    decisions: list[UnlockDecision] = []

    for index, contract in enumerate(contracts, start=1):
        score = 320 + (index * 37) % 620
        limite_credito = money(rng, 500.0, 12000.0)
        usado = round(min(limite_credito, contract.monthly_value * max(1, contract.pending_invoices)), 2)
        disponivel = round(max(0.0, limite_credito - usado), 2)
        consulta = previous_moment(rng, LAB_NOW, min_minutes=15, max_days=120)
        if index % 2 == 0:
            resultado = "APROVADO" if score >= 700 else ("ANALISE_MANUAL" if score >= 450 else "REJEITADO")
            credit_checks.append(
                CreditCheck(
                    check_id=f"CHK-{index:06d}",
                    customer_id=contract.customer_id,
                    score=score,
                    limite_credito=limite_credito,
                    usado=usado,
                    disponivel=disponivel,
                    data_consulta=consulta,
                    resultado=resultado,
                )
            )

        for inv_number in range(max(1, contract.pending_invoices)):
            emission = previous_moment(rng, LAB_NOW, min_minutes=60, max_days=220)
            due = next_moment(rng, emission, min_minutes=60, max_days=45)
            if inv_number < contract.pending_invoices:
                status = "VENCIDA" if due.date() < LAB_TODAY else "ABERTA"
                paid_at = None
            else:
                status = "PAGA"
                paid_at = next_moment(rng, due, min_minutes=30, max_days=20)
            invoices.append(
                Invoice(
                    invoice_id=f"INV-{index:06d}-{inv_number + 1:02d}",
                    customer_id=contract.customer_id,
                    valor=money(rng, 80.0, 1800.0),
                    data_emissao=emission,
                    data_vencimento=due,
                    status=status,
                    paid_at=paid_at,
                )
            )

    total_requests = LAB_MIN_RECORDS + 110
    for index in range(total_requests):
        contract = contracts[index % len(contracts)]
        score = 320 + ((index % len(contracts)) + 1) * 37 % 620
        promise_date = None
        if index % 4 == 0:
            promise_date = LAB_TODAY + timedelta(days=index % 6)
        expected, justification = expected_unlock_decision(
            contract_status=contract.contract_status,
            pending_invoices=contract.pending_invoices,
            score=score,
            promise_date=promise_date,
            today=LAB_TODAY,
        )
        requested_at = previous_moment(rng, LAB_NOW, min_minutes=10, max_days=160)
        resolved_at = None
        status = "RECEBIDO"
        decision_id = None
        if index % 5 == 0:
            status = "AGUARDANDO_PROMESSA"
        elif index % 3 == 0:
            status = "EM_ANALISE"
        if index % 6 == 0:
            decision_id = f"DEC-{index + 1:06d}"
            status = "APROVADO" if expected == "LIBERADO" else "REJEITADO"
            resolved_at = next_moment(rng, requested_at, min_minutes=30, max_days=5)
            decisions.append(
                UnlockDecision(
                    decision_id=decision_id,
                    request_id=f"UR-{index + 1:06d}",
                    decision=expected,
                    justification=justification,
                    decided_at=resolved_at,
                    credit_check_id=f"CHK-{(index % len(contracts)) + 1:06d}" if (index % len(contracts) + 1) % 2 == 0 else None,
                    score_usado=score,
                )
            )
        request = UnlockRequest(
            request_id=f"UR-{index + 1:06d}",
            customer_id=contract.customer_id,
            protocol=f"PRT-{index + 1:08d}",
            motivo=build_unlock_reason(rng),
            status=status,
            requested_at=requested_at,
            resolved_at=resolved_at,
            promessa_pagamento_data=promise_date,
            decision_id=decision_id,
            decisao_esperada=expected,
        )
        requests.append(request)
        histories.append(
            UnlockHistory(
                history_id=f"UHI-{index + 1:06d}-1",
                customer_id=contract.customer_id,
                request_id=request.request_id,
                acao="CRIAR",
                status_anterior=None,
                status_novo=status,
                executed_by="seed.bot",
                occurred_at=requested_at,
            )
        )
        if promise_date is not None:
            promise_logged = next_moment(rng, requested_at, min_minutes=15, max_days=2)
            histories.append(
                UnlockHistory(
                    history_id=f"UHI-{index + 1:06d}-2",
                    customer_id=contract.customer_id,
                    request_id=request.request_id,
                    acao="PROMESSA",
                    status_anterior="RECEBIDO",
                    status_novo="AGUARDANDO_PROMESSA",
                    executed_by="seed.bot",
                    occurred_at=promise_logged,
                )
            )
        if decision_id is not None and resolved_at is not None:
            histories.append(
                UnlockHistory(
                    history_id=f"UHI-{index + 1:06d}-3",
                    customer_id=contract.customer_id,
                    request_id=request.request_id,
                    acao="DECIDIR",
                    status_anterior="EM_ANALISE",
                    status_novo=status,
                    executed_by="seed.bot",
                    occurred_at=resolved_at,
                )
            )

    db.add_all(invoices)
    db.add_all(credit_checks)
    db.add_all(requests)
    db.add_all(histories)
    db.add_all(decisions)
    db.commit()
    logger.info("Group 08 seeded with %d unlock requests", len(requests))
