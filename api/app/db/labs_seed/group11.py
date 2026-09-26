import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group11 import (
    EMAIL_BODIES,
    OBSERVACOES_EVIDENCIA,
    PARECERES_REGISTRO,
)
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    email_address,
    group_rng,
    next_moment,
    previous_moment,
)


logger = logging.getLogger(__name__)

SISTEMAS = {
    "erp": "2.4.1",
    "crm": "5.9.0",
    "dw": "3.2.4",
    "billing": "1.18.7",
}


def _already_seeded(db: Session, model) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def _analyze(
    sistema: str, versao_depois: str | None, observacoes: str | None, resultado: str
) -> tuple[list[str], list[str], str, str]:
    divergent_fields: list[str] = []
    missing_fields: list[str] = []
    expected = SISTEMAS[sistema]
    if versao_depois != expected:
        divergent_fields.append("versao_depois")
    if sistema in {"erp", "billing"} and not observacoes:
        missing_fields.append("observacoes")
    if resultado != "SUCESSO":
        divergent_fields.append("resultado")
    decisao = "APROVADO" if not divergent_fields and not missing_fields else "REPROVADO"
    rationale = (
        "Evidencia consistente com o esperado."
        if decisao == "APROVADO"
        else "Divergencias ou campos obrigatorios ausentes na evidencia."
    )
    return divergent_fields, missing_fields, decisao, rationale


def seed_group(db: Session) -> None:
    from ...models.labs.group11_evidences import (
        ActionPlan,
        EvidenceRegistry,
        IncomingEmail,
        RestoreEvidence,
    )

    if _already_seeded(db, RestoreEvidence):
        logger.info("Group 11 already seeded")
        return

    rng = group_rng(11)
    total = LAB_MIN_RECORDS + 24
    emails: list[IncomingEmail] = []
    evidences: list[RestoreEvidence] = []
    registry_rows: list[EvidenceRegistry] = []
    action_plans: list[ActionPlan] = []
    systems = tuple(SISTEMAS)

    for index in range(total):
        number = index + 1
        recebido_em = previous_moment(rng, LAB_NOW, min_minutes=240, max_days=180)
        sistema = systems[index % len(systems)]
        ticket = f"CHG-{2000 + number}"
        emails.append(
            IncomingEmail(
                email_id=f"EML-{number:06d}",
                remetente=email_address(rng),
                assunto=f"Solicitacao de evidencia de restore {ticket}",
                corpo=EMAIL_BODIES[index % len(EMAIL_BODIES)],
                recebido_em=recebido_em,
                ticket_mudanca=ticket,
                severidade=("ALTA", "MEDIA", "BAIXA")[index % 3],
            )
        )
        evidence_time = next_moment(rng, recebido_em, min_minutes=30, max_days=10)
        versao_antes = f"{1 + index % 3}.{index % 9}.{index % 7}"
        versao_depois = SISTEMAS[sistema] if number % 5 else f"{SISTEMAS[sistema]}-rc"
        observacoes = (
            OBSERVACOES_EVIDENCIA[index % len(OBSERVACOES_EVIDENCIA)]
            if number % 6
            else None
        )
        resultado = "SUCESSO" if number % 4 else "PARCIAL" if number % 3 else "FALHA"
        divergent_fields, missing_fields, decisao, rationale = _analyze(
            sistema, versao_depois, observacoes, resultado
        )
        evidence_id = f"EVD-{number:06d}"
        ic = f"IC-{number:06d}"
        evidences.append(
            RestoreEvidence(
                evidence_id=evidence_id,
                email_id=f"EML-{number:06d}",
                IC=ic,
                data_hora_teste=evidence_time,
                resultado=resultado,
                sistema=sistema,
                versao_antes=versao_antes,
                versao_depois=versao_depois,
                duracao_seg=200 + number % 1800,
                responsavel=f"restore.owner.{number % 9}",
                observacoes=observacoes,
                has_prints=number % 4 != 0,
                divergent_fields_json=json.dumps(
                    divergent_fields, ensure_ascii=False, sort_keys=True
                ),
                missing_fields_json=json.dumps(
                    missing_fields, ensure_ascii=False, sort_keys=True
                ),
                decisao=decisao,
                rationale=rationale,
            )
        )
        status = (
            "APROVADO"
            if decisao == "APROVADO"
            else "REPROVADO"
            if number % 2
            else "EM_ANALISE"
        )
        analyzed_at = next_moment(rng, evidence_time, min_minutes=20, max_days=8)
        registry_rows.append(
            EvidenceRegistry(
                id=f"REG-{number:06d}",
                IC=ic,
                status=status,
                analisado_por=f"reviewer.{number % 7}",
                analisado_em=analyzed_at,
                parecer=PARECERES_REGISTRO[index % len(PARECERES_REGISTRO)],
            )
        )
        if decisao == "REPROVADO":
            action_created = next_moment(rng, analyzed_at, min_minutes=30, max_days=5)
            action_plans.append(
                ActionPlan(
                    id=f"ACT-{number:06d}",
                    evidence_id=evidence_id,
                    acao="Atualizar procedimento e repetir a coleta de evidencia.",
                    prazo=min(action_created.date(), LAB_NOW.date()),
                    responsavel=f"owner.sistema.{number % 5}",
                    status="CONCLUIDA" if number % 3 == 0 else "PENDENTE",
                    conclusao="Acao concluida e evidencias reenviadas."
                    if number % 3 == 0
                    else None,
                    created_at=action_created,
                    concluded_at=next_moment(
                        rng, action_created, min_minutes=90, max_days=4
                    )
                    if number % 3 == 0
                    else None,
                )
            )

    db.add_all(emails)
    db.add_all(evidences)
    db.add_all(registry_rows)
    db.add_all(action_plans)
    db.commit()
    logger.info("Group 11 seeded with %d evidences", len(evidences))
