import json
import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_leads import LEAD_CATEGORY_BY_POOL, build_lead_message
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_ORIGIN_EPOCH,
    LAB_SEED,
    LAB_TODAY,
    STATES,
    company_name,
    group_rng,
    next_moment,
    percentage,
    person_name,
    previous_moment,
    weighted,
)
from ...labs.normalize import normalize_email, normalize_phone


logger = logging.getLogger(__name__)

G01_PRODUCTS = (
    ("PROD-01", "Quantum Analytics", "enterprise"),
    ("PROD-02", "Quantum Analytics", "mid_market"),
    ("PROD-03", "Quantum Flow", "enterprise"),
    ("PROD-04", "Quantum Flow", "small_business"),
    ("PROD-05", "Quantum Guard", "public_sector"),
    ("PROD-06", "Quantum Guard", "enterprise"),
    ("PROD-07", "Quantum Insight", "startup"),
    ("PROD-08", "Quantum Insight", "mid_market"),
    ("PROD-09", "Quantum Bridge", "nonprofit"),
    ("PROD-10", "Quantum Bridge", "enterprise"),
    ("PROD-11", "Quantum Vault", "public_sector"),
    ("PROD-12", "Quantum Vault", "mid_market"),
)

G01_REP_REGIONS = (
    ("Sudeste", ("SP", "RJ", "MG")),
    ("Sul", ("PR", "SC", "RS")),
    ("Nordeste", ("BA", "PE", "CE", "RN")),
    ("Centro-Oeste", ("GO", "MT", "DF")),
    ("Norte", ("AM", "PA", "RO")),
)

G01_STATUS_OLD = ("CONVERTIDO", "DESQUALIFICADO", "DESCARTADO")
G01_STATUS_RECENT = ("NOVO", "EM_QUALIFICACAO")
G01_DUPLICATE_RATE = 0.08
G01_BLIND_RATE = 0.42
G01_INVALID_FIELD_RATE = 0.15
G01_UNKNOWN_FIELD_RATE = 0.08
G01_LLM_CONFIDENT_POOL = ("lead_high_intent", "lead_nurturing", "lead_high_value", "lead_technical", "lead_complaint")
G01_LLM_UNCERTAIN_POOL = ("lead_low_confidence", "lead_anonymous", "lead_uninterested")
G01_DISQUALIFY_REASONS = (
    "Sem orcamento aprovado",
    "Fora do ICP do trimestre",
    "Solicitou nao ser contatado",
    "Ja contratou concorrente",
    "E-mail invalido e sem telefone",
    "Aguarda approvecao juridica sem previsao",
    "Regiao fora da area de atuacao",
)


def _already_seeded(db: Session, model) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def seed_group(db: Session) -> None:
    from ...models.labs.group01_leads import Campaign, Lead, Product, SalesRep

    if _already_seeded(db, Lead):
        logger.info("Group 01 already seeded (%s leads)", LAB_SEED)
        return

    rng = group_rng(1)

    products = [
        Product(product_id=product_id, nome=nome, segmento=segmento)
        for product_id, nome, segmento in G01_PRODUCTS
    ]
    db.add_all(products)

    reps: list[SalesRep] = []
    for index in range(14):
        regiao, estados = G01_REP_REGIONS[index % len(G01_REP_REGIONS)]
        nome = person_name(rng)
        reps.append(
            SalesRep(
                sales_rep_id=f"SR-{index + 1:02d}",
                nome=nome,
                email=normalize_email(f"rep.{index + 1:02d}@example.com"),
                regioes=json.dumps([regiao, *list(estados)]),
                segmentos=json.dumps(
                    sorted({rng.choice(("enterprise", "mid_market", "small_business", "startup")) for _ in range(2)})
                ),
                produtos=json.dumps(sorted({rng.choice([item[0] for item in G01_PRODUCTS]) for _ in range(3)})),
                active=index not in (6, 13),
            )
        )
    db.add_all(reps)

    campaigns = [
        Campaign(
            campaign_id=f"CMP-{index + 1:03d}",
            nome=f"Campanha {G01_PRODUCTS[index % len(G01_PRODUCTS)][1]} {index + 1:03d}",
            origem=("site", "linkedin", "evento", "email_marketing", "parceiro", "indicacao")[index % 6],
            produto=G01_PRODUCTS[index % len(G01_PRODUCTS)][0],
            active=index % 7 != 6,
        )
        for index in range(12)
    ]
    db.add_all(campaigns)
    db.flush()

    active_reps = [rep for rep in reps if rep.active]
    product_ids = [product.product_id for product in products]
    origin_cycle = ("site", "indicacao", "linkedin", "evento", "email_marketing", "outbound", "whatsapp", "parceiro")
    quality_weights = (
        ("lead_high_intent", 22),
        ("lead_nurturing", 18),
        ("lead_high_value", 10),
        ("lead_technical", 14),
        ("lead_complaint", 8),
        ("lead_uninterested", 12),
        ("lead_anonymous", 8),
        ("lead_low_confidence", 8),
    )

    total = LAB_MIN_RECORDS + 84
    duplicate_total = int(total * G01_DUPLICATE_RATE)
    unique_total = total - duplicate_total

    leads: list[Lead] = []
    source_pool: list[Lead] = []

    for index in range(total):
        lead_number = index + 1
        is_duplicate = index >= unique_total
        quality = weighted(rng, quality_weights)
        created_at = previous_moment(rng, LAB_ORIGIN_EPOCH + timedelta(hours=23, minutes=59), min_minutes=1, max_days=400)

        if is_duplicate and source_pool:
            template = source_pool[rng.randrange(len(source_pool))]
            nome = template.nome
            empresa = template.empresa
            email = template.email
            telefone = template.telefone
            origem = rng.choice(origin_cycle)
            segmento = template.segmento
            regiao = template.regiao
            produto_interesse = template.produto_interesse
            mensagem = template.mensagem
            duplicate_key = template.duplicate_key
            created_at = max(
                created_at,
                next_moment(rng, template.created_at, min_minutes=30),
            )
        else:
            segmento = rng.choice(("enterprise", "mid_market", "small_business", "startup", "public_sector", "nonprofit"))
            regiao = rng.choice(STATES)
            produto_interesse = rng.choice(product_ids)
            origem = rng.choice(origin_cycle)

            if quality == "lead_anonymous":
                nome = None
                empresa = None
                email = None
                telefone = None
            else:
                nome = person_name(rng)
                empresa = company_name(rng)
                email = normalize_email(f"lead.{lead_number:04d}@example.com")
                telefone = None if rng.random() < G01_INVALID_FIELD_RATE else f"({rng.randint(11, 85)}) 9{rng.randint(1000000, 9999999)}"

            mensagem = build_lead_message(rng, quality)
            if email:
                duplicate_key = normalize_email(email)
            elif telefone:
                duplicate_key = normalize_phone(telefone)
            else:
                duplicate_key = f"lead:{lead_number:06d}"

        if rng.random() < G01_UNKNOWN_FIELD_RATE:
            mensagem = f"{mensagem} Interesse em escolher plano por regiao especifica sem informar o estado."
        if rng.random() < G01_INVALID_FIELD_RATE and email:
            email = rng.choice(("nao-e-email", "sem-arroba-example.com", " Lead 4000@exemplo ", "@example.com"))

        age_days = (LAB_TODAY - created_at.date()).days
        if age_days <= 30:
            status = rng.choice(G01_STATUS_RECENT)
        else:
            status = rng.choice(G01_STATUS_OLD)
            if rng.random() < 0.35:
                status = "EM_QUALIFICACAO"

        updated_at = next_moment(rng, created_at, min_minutes=15, max_days=12)
        if status in ("NOVO",):
            updated_at = created_at
        responsavel = rng.choice(active_reps).sales_rep_id if rng.random() < 0.88 else None
        ultimo_contato_em = next_moment(rng, created_at, min_minutes=30, max_days=20) if status != "NOVO" and rng.random() < 0.8 else None

        lead = Lead(
            lead_id=f"LEAD-{lead_number:06d}",
            nome=nome,
            empresa=empresa,
            email=email,
            telefone=telefone,
            origem=origem,
            segmento=segmento,
            regiao=regiao,
            produto_interesse=produto_interesse,
            mensagem=mensagem,
            status=status,
            responsavel=responsavel,
            created_at=created_at,
            updated_at=updated_at,
            ultimo_contato_em=ultimo_contato_em,
            categoria_sugerida=None,
            resumo_llm=None,
            confianca_llm=None,
            qualificado=None,
            motivo_desqualificacao=None,
            duplicate_key=duplicate_key,
        )
        leads.append(lead)
        if not is_duplicate:
            source_pool.append(lead)

    for lead in leads:
        if rng.random() < G01_BLIND_RATE:
            continue
        pool = G01_LLM_CONFIDENT_POOL if rng.random() < 0.82 else G01_LLM_UNCERTAIN_POOL
        quality = rng.choice(pool)
        categoria, aprovado = LEAD_CATEGORY_BY_POOL[quality]
        confianca = percentage(rng, 0.62, 0.98) if pool == G01_LLM_CONFIDENT_POOL else percentage(rng, 0.21, 0.61)
        lead.categoria_sugerida = categoria
        lead.confianca_llm = confianca
        lead.qualificado = 1 if aprovado else 0
        lead.resumo_llm = (
            f"Lead de {lead.origem} com interesse em {categoria.replace('_', ' ')}; "
            f"confianca do modelo {confianca:.2f}."
        )
        if not aprovado and lead.status in ("DESQUALIFICADO", "DESCARTADO"):
            lead.motivo_desqualificacao = rng.choice(G01_DISQUALIFY_REASONS)
        elif lead.status == "DESQUALIFICADO":
            lead.motivo_desqualificacao = rng.choice(G01_DISQUALIFY_REASONS)

    db.add_all(leads)
    db.commit()
    logger.info("Group 01 seeded with %d leads (%d duplicates)", len(leads), duplicate_total)
