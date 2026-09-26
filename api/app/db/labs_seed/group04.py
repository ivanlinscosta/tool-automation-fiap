import hashlib
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group04 import build_customer_message
from ...labs.generators import (
    CHANNELS,
    LAB_MIN_RECORDS,
    LAB_NOW,
    group_rng,
    next_moment,
    previous_moment,
)


logger = logging.getLogger(__name__)

INTENTS = (
    "cancelamento",
    "troca",
    "duvida_produto",
    "reclamacao",
    "elogio",
    "reclamacao_financ",
    "upgrade",
)
INTENT_DEPARTMENT = {
    "cancelamento": "DEP-01",
    "troca": "DEP-02",
    "duvida_produto": "DEP-03",
    "reclamacao": "DEP-04",
    "elogio": "DEP-05",
    "reclamacao_financ": "DEP-06",
    "upgrade": "DEP-07",
}
DEPARTMENTS = (
    (
        "DEP-01",
        "Retencao",
        "Equipe responsavel por cancelamentos e risco de churn.",
        4,
        True,
    ),
    ("DEP-02", "Pos-Venda", "Atende trocas e ajustes de pedidos ou servicos.", 8, True),
    (
        "DEP-03",
        "Especialistas de Produto",
        "Orienta duvidas tecnicas e comerciais sobre o catalogo.",
        12,
        True,
    ),
    ("DEP-04", "Ouvidoria", "Trata reclamacoes gerais com maior criticidade.", 6, True),
    (
        "DEP-05",
        "Relacionamento",
        "Consolida elogios e programas de experiencia.",
        24,
        True,
    ),
    (
        "DEP-06",
        "Financeiro",
        "Analisa cobranca, desconto e divergencias financeiras.",
        4,
        True,
    ),
    (
        "DEP-07",
        "Expansao",
        "Trata upgrade, cross-sell e ampliacao de contratos.",
        8,
        True,
    ),
    (
        "DEP-08",
        "Fila Desativada",
        "Departamento mantido apenas para exercicios de validacao.",
        24,
        False,
    ),
)


def _already_seeded(db: Session, model: type) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def _impact_urgency(intent: str, index: int) -> tuple[str, str]:
    if intent in {"cancelamento", "reclamacao_financ"}:
        return ("alto", "alto" if index % 2 == 0 else "medio")
    if intent == "reclamacao":
        return ("alto", "medio")
    if intent == "upgrade":
        return ("medio", "alto")
    if intent == "troca":
        return ("medio", "medio")
    if intent == "duvida_produto":
        return ("baixo", "medio")
    return ("baixo", "baixo")


def _priority(intent: str, impacto: str, urgencia: str) -> tuple[str, int]:
    if intent in {"cancelamento", "reclamacao_financ"} and "alto" in {
        impacto,
        urgencia,
    }:
        return "P1", 4
    if impacto == "alto" and urgencia == "alto":
        return "P1", 4
    if impacto == "alto" or urgencia == "alto":
        return "P2", 8
    if impacto == "medio" or urgencia == "medio":
        return "P3", 16
    return "P4", 24


def _confidence(intent: str, message: str) -> float:
    digest = hashlib.sha1(f"{intent}:{message}".encode("utf-8")).hexdigest()
    bucket = int(digest[:4], 16) / 0xFFFF
    return round(0.6 + bucket * 0.39, 4)


def seed_group(db: Session) -> None:
    from ...models.labs.group04_support import CustomerEvent, Department

    if _already_seeded(db, CustomerEvent):
        logger.info("Group 04 already seeded")
        return

    rng = group_rng(4)
    departments = [
        Department(
            department_id=department_id,
            nome=nome,
            descricao=descricao,
            sla_horas_padrao=sla_horas_padrao,
            ativo=ativo,
        )
        for department_id, nome, descricao, sla_horas_padrao, ativo in DEPARTMENTS
    ]
    db.add_all(departments)

    total_events = LAB_MIN_RECORDS + 144
    events: list[CustomerEvent] = []
    for index in range(1, total_events + 1):
        intent = INTENTS[(index - 1) % len(INTENTS)]
        impacto, urgencia = _impact_urgency(intent, index)
        prioridade, sla_horas = _priority(intent, impacto, urgencia)
        created_at = previous_moment(rng, LAB_NOW, min_minutes=20, max_days=610)
        message = build_customer_message(rng, intent)
        confidence = _confidence(intent, message)
        department = None if index % 6 == 0 else INTENT_DEPARTMENT[intent]
        status = (
            "novo" if department is None else ("roteado" if index % 5 else "resolvido")
        )
        resolved_at = None
        if status == "resolvido":
            resolved_at = next_moment(rng, created_at, min_minutes=30, max_days=10)
        events.append(
            CustomerEvent(
                event_id=f"EVT-{index:06d}",
                customer_id=f"CUS-LAB-{4000 + ((index - 1) % 280):05d}",
                canal=CHANNELS[(index - 1) % len(CHANNELS)],
                mensagem=message,
                intencao=intent,
                prioridade=prioridade,
                confianca=confidence,
                sla_horas=sla_horas,
                departamento=department,
                impacto=impacto,
                urgencia=urgencia,
                created_at=created_at,
                resolved_at=resolved_at,
                status=status,
            )
        )

    db.add_all(events)
    db.commit()
    logger.info("Group 04 seeded with %d customer events", len(events))
