import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group07 import build_collection_message
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    brazilian_phone,
    cnpj,
    cpf,
    group_rng,
    is_valid_cnpj,
    is_valid_cpf,
    money,
    next_moment,
    person_name,
    previous_moment,
)
from ...models.labs.group07_cobranca import CollectionConfig, CollectionHistory, Receivable, faixa_label


logger = logging.getLogger(__name__)


def _already_seeded(db: Session) -> bool:
    return db.execute(select(func.count()).select_from(Receivable)).scalar_one() > 0


def seed_group(db: Session) -> None:
    if _already_seeded(db):
        logger.info("Group 07 already seeded")
        return

    rng = group_rng(7)

    configs = [
        CollectionConfig(config_id="CFG-0001", faixa_inicio=1, faixa_fim=15, acao="ENVIAR_EMAIL", canal="email", ativo=True, template_mensagem="Lembrete amigavel de vencimento recente.", ordem=1),
        CollectionConfig(config_id="CFG-0002", faixa_inicio=16, faixa_fim=30, acao="ENVIAR_SMS", canal="sms", ativo=True, template_mensagem="Aviso por SMS para atraso intermediario.", ordem=2),
        CollectionConfig(config_id="CFG-0003", faixa_inicio=31, faixa_fim=60, acao="LIGAR", canal="phone", ativo=True, template_mensagem="Acionar contato telefonico para negociacao.", ordem=3),
        CollectionConfig(config_id="CFG-0004", faixa_inicio=61, faixa_fim=90, acao="ENVIAR_EMAIL", canal="email", ativo=True, template_mensagem="Escalada formal de cobranca por e-mail.", ordem=4),
        CollectionConfig(config_id="CFG-0005", faixa_inicio=91, faixa_fim=None, acao="SUSPENDER", canal="workflow", ativo=True, template_mensagem="Conta sujeita a suspensao automatica.", ordem=5),
    ]
    db.add_all(configs)
    db.flush()

    bucket_days = [0, 0, 0, 3, 8, 12, 18, 27, 36, 52, 74, 108, 140]
    receivables: list[Receivable] = []
    histories: list[CollectionHistory] = []
    total = LAB_MIN_RECORDS + 150

    for index in range(total):
        dias_atraso = bucket_days[index % len(bucket_days)]
        customer_document = cpf(rng, valid=index % 10 != 0) if index % 4 != 0 else cnpj(rng, valid=index % 9 != 0)
        customer_phone = None if index % 11 == 0 else brazilian_phone(rng)
        valor = money(rng, 120.0, 28000.0)
        data_vencimento = min(LAB_NOW, previous_moment(rng, LAB_NOW, min_minutes=60, max_days=220)) - timedelta(days=dias_atraso)
        data_emissao = previous_moment(rng, data_vencimento, min_minutes=60, max_days=400)

        if dias_atraso == 0 and index % 5 == 0:
            status = "PAGO"
        elif dias_atraso == 0 and index % 8 == 0:
            status = "CANCELADO"
        elif dias_atraso == 0:
            status = "ABERTO"
        else:
            status = "VENCIDO"

        paid_at = next_moment(rng, data_vencimento, min_minutes=30, max_days=20) if status == "PAGO" else None
        valor_pago = valor if status == "PAGO" else None
        bucket = faixa_label(dias_atraso)
        deve_enviar = status == "VENCIDO" and bucket != "em_dia"
        updated_at = paid_at or next_moment(rng, data_emissao, min_minutes=30, max_days=40)

        receivable = Receivable(
            id_titulo=f"TIT-{index + 1:06d}",
            customer_id=f"CLI-{(index % 420) + 1:05d}",
            customer_name=person_name(rng),
            customer_document=customer_document,
            customer_phone=customer_phone,
            valor=valor,
            data_emissao=data_emissao,
            data_vencimento=data_vencimento,
            status=status,
            dias_atraso=dias_atraso,
            valor_pago=valor_pago,
            paid_at=paid_at,
            deve_enviar=deve_enviar,
            updated_at=updated_at,
        )
        receivables.append(receivable)

        if deve_enviar and index % 3 == 0:
            config = configs[0]
            for candidate in configs:
                upper = candidate.faixa_fim if candidate.faixa_fim is not None else 10_000
                if candidate.faixa_inicio <= dias_atraso <= upper:
                    config = candidate
                    break
            sent_at = next_moment(rng, data_vencimento, min_minutes=120, max_days=20)
            result = "SUCESSO"
            motivo = None
            if config.canal == "sms" and customer_phone is None:
                result = "FALHA"
                motivo = "cliente nao possui telefone"
            elif config.canal == "phone" and index % 7 == 0:
                result = "FALHA"
                motivo = "canal indisponivel"
            elif config.acao == "SUSPENDER" and not (is_valid_cpf(customer_document) or is_valid_cnpj(customer_document)):
                result = "IGNORADO"
                motivo = "documento invalido para suspensao"
            histories.append(
                CollectionHistory(
                    id=f"HIS-{index + 1:06d}",
                    id_titulo=receivable.id_titulo,
                    config_id=config.config_id,
                    acao=config.acao,
                    canal=config.canal,
                    mensagem_enviada=build_collection_message(rng, config.acao, receivable.id_titulo, valor),
                    enviada_em=sent_at,
                    resultado=result,
                    respondedido=result != "FALHA",
                    motivo=motivo,
                )
            )

    db.add_all(receivables)
    db.add_all(histories)
    db.commit()
    logger.info("Group 07 seeded with %d receivables", len(receivables))
