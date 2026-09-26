import hashlib
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group03 import (
    GROUP03_LINE_TEMPLATES,
    GROUP03_LOAD_LOG_INFO,
    GROUP03_LOAD_LOG_WARN,
    GROUP03_VALIDATION_CNPJ,
    GROUP03_VALIDATION_OK,
    GROUP03_VALIDATION_PRODUCT,
    GROUP03_VALIDATION_VALUE,
)
from ...labs.generators import (
    LAB_NOW,
    cnpj,
    company_name,
    email_address,
    group_rng,
    is_valid_cnpj,
    money,
    next_moment,
    person_name,
    previous_moment,
)


logger = logging.getLogger(__name__)

PRODUCT_PIPELINES = (
    ("CRM Enterprise", "PIPE-ENT", "qualificado", True),
    ("CRM SMB", "PIPE-SMB", "novo", True),
    ("Analytics Pro", "PIPE-DATA", "proposta", True),
    ("Servicos Onboarding", "PIPE-SVC", "qualificado", True),
    ("FinOps Suite", "PIPE-FIN", "novo", True),
    ("Retention Desk", "PIPE-CS", "proposta", False),
)
STAGES = ("novo", "qualificado", "proposta", "ganho", "perdido")
UNMAPPED_PRODUCTS = ("Produto Sem Mapa", "Pacote Inexistente", "CRM Legacy")


def _already_seeded(db: Session, model: type) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def _bitrix_id(opportunity_id: str) -> str:
    digest = hashlib.sha1(opportunity_id.encode("utf-8")).hexdigest()[:12].upper()
    return f"BTRX-{digest}"


def seed_group(db: Session) -> None:
    from ...models.labs.group03_bitrix import (
        AuthorizedRequester,
        CrmContact,
        CrmDeal,
        CrmUser,
        Load,
        LoadLog,
        Opportunity,
        OpportunityValidation,
        ProductPipelineMap,
    )

    if _already_seeded(db, Opportunity):
        logger.info("Group 03 already seeded")
        return

    rng = group_rng(3)

    requesters = [
        AuthorizedRequester(
            requester_id=f"REQ-{index + 1:03d}",
            nome=person_name(rng),
            email=f"revops.{index + 1:02d}@example.com",
            area=("revops", "inside_sales", "marketing_ops")[index % 3],
            ativo=index not in (7, 10),
        )
        for index in range(12)
    ]
    maps = [
        ProductPipelineMap(
            map_id=f"MAP-{index + 1:03d}",
            produto=produto,
            pipeline_codigo=pipeline,
            etapa_padrao=etapa,
            ativo=ativo,
        )
        for index, (produto, pipeline, etapa, ativo) in enumerate(PRODUCT_PIPELINES)
    ]
    crm_users = [
        CrmUser(
            crm_user_id=f"CRMU-{index + 1:03d}",
            nome=person_name(rng),
            email=f"crm.user.{index + 1:02d}@example.com",
            ativo=index != 5,
        )
        for index in range(6)
    ]
    db.add_all(requesters)
    db.add_all(maps)
    db.add_all(crm_users)

    valid_products = [item[0] for item in PRODUCT_PIPELINES if item[3]]
    active_requesters = [item for item in requesters if item.ativo]
    active_crm_users = [item for item in crm_users if item.ativo]
    total_loads = 48
    lines_per_load = 24

    loads: list[Load] = []
    opportunities: list[Opportunity] = []
    validations: list[OpportunityValidation] = []
    contacts: list[CrmContact] = []
    deals: list[CrmDeal] = []
    logs: list[LoadLog] = []
    opportunity_number = 0
    contact_number = 0
    deal_number = 0
    log_number = 0

    for load_number in range(1, total_loads + 1):
        load_id = f"LOAD-{load_number:04d}"
        load_created_at = previous_moment(rng, LAB_NOW, min_minutes=120, max_days=650)
        load_updated_at = next_moment(rng, load_created_at, min_minutes=15, max_days=5)
        requester = active_requesters[(load_number - 1) % len(active_requesters)]
        lines: list[str] = []
        load_opportunities: list[Opportunity] = []
        load_validations: list[OpportunityValidation] = []
        load_contacts: list[CrmContact] = []
        load_deals: list[CrmDeal] = []
        invalid_lines = 0

        for line_number in range(1, lines_per_load + 1):
            opportunity_number += 1
            opportunity_id = f"OPP-{opportunity_number:06d}"
            company = company_name(rng)
            contact_name = person_name(rng)
            contact_email = email_address(rng, contact_name, "example.com")
            cnpj_is_valid = line_number % 7 != 0
            value_is_valid = line_number % 9 != 0
            product_is_mapped = line_number % 8 != 0
            product = (
                valid_products[(opportunity_number - 1) % len(valid_products)]
                if product_is_mapped
                else UNMAPPED_PRODUCTS[(line_number - 1) % len(UNMAPPED_PRODUCTS)]
            )
            stage = STAGES[(opportunity_number - 1) % len(STAGES)]
            value = money(rng, 15000, 250000)
            if not value_is_valid:
                value = 0.0
            document = cnpj(rng, valid=cnpj_is_valid)
            row_text = GROUP03_LINE_TEMPLATES[0].format(
                empresa=company,
                cnpj=document,
                produto=product,
                valor=f"{value:.2f}",
                contato=contact_name,
                email=contact_email,
                stage=stage,
            )
            lines.append(row_text)

            opportunity_created_at = max(
                load_created_at,
                previous_moment(rng, LAB_NOW, min_minutes=30, max_days=620),
            )
            opportunity_updated_at = next_moment(
                rng, opportunity_created_at, min_minutes=5, max_days=4
            )
            opportunity = Opportunity(
                opportunity_id=opportunity_id,
                load_id=load_id,
                line_number=line_number,
                empresa=company,
                cnpj=document,
                produto=product,
                valor=value,
                contato_nome=contact_name,
                contato_email=contact_email,
                stage=stage,
                created_at=opportunity_created_at,
                updated_at=opportunity_updated_at,
            )
            load_opportunities.append(opportunity)

            if not cnpj_is_valid:
                invalid_lines += 1
                reason_pool = GROUP03_VALIDATION_CNPJ
            elif not value_is_valid:
                invalid_lines += 1
                reason_pool = GROUP03_VALIDATION_VALUE
            elif not product_is_mapped:
                invalid_lines += 1
                reason_pool = GROUP03_VALIDATION_PRODUCT
            else:
                reason_pool = GROUP03_VALIDATION_OK

            validation_created_at = next_moment(
                rng, opportunity_created_at, min_minutes=5, max_days=2
            )
            validation_updated_at = next_moment(
                rng, validation_created_at, min_minutes=5, max_days=1
            )
            validation = OpportunityValidation(
                validation_id=f"VAL-{opportunity_number:06d}",
                opportunity_id=opportunity_id,
                cnpj_valido=cnpj_is_valid,
                valor_valido=value_is_valid,
                produto_mapeado=product_is_mapped,
                motivo=rng.choice(reason_pool),
                created_at=validation_created_at,
                updated_at=validation_updated_at,
            )
            load_validations.append(validation)

            contact_number += 1
            owner = active_crm_users[(contact_number - 1) % len(active_crm_users)]
            contact_created_at = next_moment(
                rng, opportunity_created_at, min_minutes=3, max_days=2
            )
            contact_updated_at = next_moment(
                rng, contact_created_at, min_minutes=3, max_days=1
            )
            contact = CrmContact(
                contact_id=f"CTT-{contact_number:06d}",
                nome=contact_name,
                email=contact_email,
                empresa=company,
                cnpj=document,
                owner_user_id=owner.crm_user_id,
                created_at=contact_created_at,
                updated_at=contact_updated_at,
            )
            load_contacts.append(contact)

            if cnpj_is_valid and value_is_valid and product_is_mapped:
                deal_number += 1
                pipeline = next(
                    item[1] for item in PRODUCT_PIPELINES if item[0] == product
                )
                deal_created_at = next_moment(
                    rng, contact_created_at, min_minutes=5, max_days=2
                )
                deal_updated_at = next_moment(
                    rng, deal_created_at, min_minutes=5, max_days=1
                )
                load_deals.append(
                    CrmDeal(
                        deal_id=f"DEAL-{deal_number:06d}",
                        contact_id=contact.contact_id,
                        opportunity_id=opportunity_id,
                        load_id=load_id,
                        pipeline_codigo=pipeline,
                        stage=stage,
                        valor=value,
                        bitrix_id=_bitrix_id(opportunity_id),
                        created_at=deal_created_at,
                        updated_at=deal_updated_at,
                    )
                )
            assert is_valid_cnpj(document) is cnpj_is_valid

        status = "PARCIAL" if invalid_lines else "PROCESSADO"
        payload_text = "\n".join(lines)
        loads.append(
            Load(
                carga_id=load_id,
                requester_email=requester.email,
                lista_free_text=payload_text,
                chave_idempotencia=f"seed-load-{load_number:04d}",
                payload_hash=hashlib.sha1(payload_text.encode("utf-8")).hexdigest(),
                status=status,
                opportunities_count=len(load_opportunities),
                deals_created=len(load_deals),
                created_at=load_created_at,
                updated_at=load_updated_at,
            )
        )

        log_number += 1
        logs.append(
            LoadLog(
                log_id=f"LOG-{log_number:06d}",
                carga_id=load_id,
                level="INFO",
                message=GROUP03_LOAD_LOG_INFO[0],
                created_at=load_created_at,
            )
        )
        if invalid_lines:
            log_number += 1
            logs.append(
                LoadLog(
                    log_id=f"LOG-{log_number:06d}",
                    carga_id=load_id,
                    level="WARN",
                    message=GROUP03_LOAD_LOG_WARN[0],
                    created_at=next_moment(
                        rng, load_created_at, min_minutes=10, max_days=1
                    ),
                )
            )
        log_number += 1
        logs.append(
            LoadLog(
                log_id=f"LOG-{log_number:06d}",
                carga_id=load_id,
                level="INFO",
                message=GROUP03_LOAD_LOG_INFO[1],
                created_at=next_moment(rng, load_updated_at, min_minutes=5, max_days=1),
            )
        )

        opportunities.extend(load_opportunities)
        validations.extend(load_validations)
        contacts.extend(load_contacts)
        deals.extend(load_deals)

    db.add_all(loads)
    db.flush()
    db.add_all(opportunities)
    db.add_all(validations)
    db.add_all(contacts)
    db.add_all(deals)
    db.add_all(logs)
    db.commit()
    logger.info(
        "Group 03 seeded with %d opportunities across %d loads",
        len(opportunities),
        len(loads),
    )
