import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group09 import MOTIVOS_EXCECAO, PARECERES_SEGURANCA, TASK_TITLES
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    cpf,
    group_rng,
    next_moment,
    person_name,
    previous_moment,
)


logger = logging.getLogger(__name__)

DEPARTAMENTOS = ("Tecnologia", "Financeiro", "RH", "Operacoes", "Jurídico", "Marketing")
CARGOS = (
    "Analista de Dados",
    "Analista Financeiro",
    "Business Partner RH",
    "Coordenador de Operacoes",
    "Especialista em Seguranca",
    "Analista de Marketing",
)
RESPONSAVEIS_RH = ("ana.rh", "bruno.rh", "carla.rh", "diego.rh")
SISTEMAS = ("hris", "erp-financeiro", "crm", "bi", "service-desk")
PERFIS = ("basico", "analista", "gestor")
MODELOS_NOTEBOOK = ("QuantumBook Pro 14", "QuantumBook Air 13")
MODELOS_MONITOR = ("QuantumView 24", "QuantumView 27")
MODELOS_CELULAR = ("QuantumPhone 14", "QuantumPhone 15")
MODELOS_HEADSET = ("QuantumSound Office", "QuantumSound Lite")
MODELOS_CRACHA = ("Cracha RFID Padrao", "Cracha RFID Premium")


def _already_seeded(db: Session, model) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def _equipment_model(tipo: str, index: int) -> str:
    pools = {
        "NOTEBOOK": MODELOS_NOTEBOOK,
        "MONITOR": MODELOS_MONITOR,
        "CELULAR": MODELOS_CELULAR,
        "HEADSET": MODELOS_HEADSET,
        "CRACHA": MODELOS_CRACHA,
    }
    options = pools[tipo]
    return options[index % len(options)]


def seed_group(db: Session) -> None:
    from ...models.labs.group09_onboarding import (
        AccessMatrix,
        Candidate,
        Equipment,
        Onboarding,
        OnboardingTask,
        SecurityApproval,
    )

    if _already_seeded(db, Candidate):
        logger.info("Group 09 already seeded")
        return

    rng = group_rng(9)
    total = LAB_MIN_RECORDS + 32
    candidates: list[Candidate] = []
    onboardings: list[Onboarding] = []
    approvals: list[SecurityApproval] = []
    equipment_rows: list[Equipment] = []
    access_rows: list[AccessMatrix] = []
    tasks: list[OnboardingTask] = []

    for index in range(total):
        number = index + 1
        created_at = previous_moment(rng, LAB_NOW, min_minutes=180, max_days=420)
        updated_at = next_moment(rng, created_at, min_minutes=15, max_days=25)
        has_exception = number % 9 == 0
        cpf_valid = number % 7 != 0
        decision = "APROVAR" if cpf_valid or has_exception else "REJEITAR"
        status = (
            "REJEITADO"
            if decision == "REJEITAR"
            else (
                "CONCLUIDO"
                if number % 6 == 0
                else "EM_ONBOARDING"
                if number % 4 == 0
                else "APROVADO"
            )
        )
        nome = person_name(rng)
        email = f"candidate.{number:05d}@example.com"
        candidate = Candidate(
            id_candidato=f"CAND-{number:05d}",
            nome=nome,
            email=email,
            cpf=cpf(rng, valid=cpf_valid),
            cargo=CARGOS[index % len(CARGOS)],
            departamento=DEPARTAMENTOS[index % len(DEPARTAMENTOS)],
            data_admissao=updated_at.date(),
            status=status,
            admissao_excecao=has_exception,
            admissao_motivo=MOTIVOS_EXCECAO[index % len(MOTIVOS_EXCECAO)]
            if has_exception
            else None,
            decisao_admissao_esperada=decision,
            created_at=created_at,
            updated_at=updated_at,
        )
        candidates.append(candidate)

        onboarding_created = next_moment(rng, created_at, min_minutes=5, max_days=10)
        onboarding_updated = next_moment(
            rng, onboarding_created, min_minutes=10, max_days=12
        )
        onboardings.append(
            Onboarding(
                id_onboarding=f"ONB-{number:05d}",
                id_candidato=candidate.id_candidato,
                data_inicio=onboarding_created.date(),
                data_fim_prevista=min(
                    onboarding_created.date() + timedelta(days=7 + number % 8),
                    LAB_NOW.date(),
                ),
                status="CONCLUIDO"
                if status == "CONCLUIDO"
                else "EM_ANDAMENTO"
                if status in {"EM_ONBOARDING", "APROVADO"}
                else "BLOQUEADO",
                responsavel_rh=RESPONSAVEIS_RH[index % len(RESPONSAVEIS_RH)],
                created_at=onboarding_created,
                updated_at=onboarding_updated,
            )
        )

        all_security_clear = decision == "APROVAR"
        for approval_index, approval_type in enumerate(
            ("BACKGROUND_CHECK", "RG_CPF", "ANTECEDENTES", "ACESSO_PRECIFICADO")
        ):
            approval_created = next_moment(
                rng, created_at, min_minutes=10 + approval_index, max_days=5
            )
            approval_updated = next_moment(
                rng, approval_created, min_minutes=5, max_days=5
            )
            if all_security_clear:
                approval_status = (
                    "EXCEPCAO_APROVADA"
                    if has_exception and approval_type == "BACKGROUND_CHECK"
                    else "APROVADO"
                )
            elif approval_type == "RG_CPF":
                approval_status = "REPROVADO"
            else:
                approval_status = "PENDENTE"
            approvals.append(
                SecurityApproval(
                    id=f"SAP-{number:05d}-{approval_index + 1}",
                    candidate_id=candidate.id_candidato,
                    tipo_verificacao=approval_type,
                    status=approval_status,
                    verificado_por=None
                    if approval_status == "PENDENTE"
                    else f"seg.{approval_index + 1}",
                    verificado_em=None
                    if approval_status == "PENDENTE"
                    else approval_updated,
                    parecer=(
                        MOTIVOS_EXCECAO[index % len(MOTIVOS_EXCECAO)]
                        if approval_status == "EXCEPCAO_APROVADA"
                        else PARECERES_SEGURANCA[
                            (index + approval_index) % len(PARECERES_SEGURANCA)
                        ]
                    ),
                    created_at=approval_created,
                    updated_at=approval_updated,
                )
            )

        base_equipment = (
            ("NOTEBOOK", "CRACHA") if number % 3 else ("NOTEBOOK", "MONITOR", "CRACHA")
        )
        for equipment_index, equipment_type in enumerate(base_equipment):
            equipment_created = next_moment(rng, created_at, min_minutes=15, max_days=8)
            equipment_updated = next_moment(
                rng, equipment_created, min_minutes=10, max_days=8
            )
            equipment_status = (
                "EMPRESTADO"
                if all_security_clear and equipment_type != "MONITOR"
                else "SOLICITADO"
            )
            equipment_rows.append(
                Equipment(
                    id=f"EQP-{number:05d}-{equipment_index + 1}",
                    candidate_id=candidate.id_candidato,
                    tipo=equipment_type,
                    modelo=_equipment_model(equipment_type, index + equipment_index),
                    serial=f"G09-{number:05d}-{equipment_index + 1}",
                    status=equipment_status,
                    solicitacao_motivo="Kit padrao de admissao"
                    if equipment_type != "MONITOR"
                    else "Complemento ergonomico",
                    created_at=equipment_created,
                    updated_at=equipment_updated,
                )
            )

        access_level = (
            "ADMIN" if number % 8 == 0 else "ESCRITA" if number % 3 == 0 else "LEITURA"
        )
        access_approved = access_level != "ADMIN" or all_security_clear
        access_created = next_moment(rng, created_at, min_minutes=20, max_days=6)
        access_updated = next_moment(rng, access_created, min_minutes=5, max_days=6)
        access_rows.append(
            AccessMatrix(
                id=f"ACC-{number:05d}-1",
                candidate_id=candidate.id_candidato,
                sistema=SISTEMAS[index % len(SISTEMAS)],
                perfil=PERFIS[index % len(PERFIS)],
                nivel_acesso=access_level,
                aprovado=access_approved,
                aprovador="gestor.ti" if access_approved else None,
                data_aprovacao=access_updated if access_approved else None,
                created_at=access_created,
                updated_at=access_updated,
            )
        )

        for task_index, (categoria, titulo) in enumerate(TASK_TITLES):
            task_created = next_moment(
                rng, created_at, min_minutes=10 + task_index, max_days=6
            )
            task_due = next_moment(rng, task_created, min_minutes=120, max_days=10)
            concluded = all_security_clear and task_index < 3
            concluded_at = (
                next_moment(rng, task_created, min_minutes=30, max_days=4)
                if concluded
                else None
            )
            task_updated = concluded_at or next_moment(
                rng, task_created, min_minutes=5, max_days=5
            )
            tasks.append(
                OnboardingTask(
                    id=f"TSK-{number:05d}-{task_index + 1}",
                    candidate_id=candidate.id_candidato,
                    titulo=titulo,
                    categoria=categoria,
                    responsavel="rh.operacoes"
                    if categoria in {"cadastro", "documentacao"}
                    else "ti.seg",
                    prazo=task_due,
                    concluida=concluded,
                    concluida_em=concluded_at,
                    ordem=task_index + 1,
                    created_at=task_created,
                    updated_at=task_updated,
                )
            )

    db.add_all(candidates)
    db.add_all(onboardings)
    db.add_all(approvals)
    db.add_all(equipment_rows)
    db.add_all(access_rows)
    db.add_all(tasks)
    db.commit()
    logger.info("Group 09 seeded with %d candidates", len(candidates))
