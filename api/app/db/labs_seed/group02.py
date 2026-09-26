import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.corpus_group02 import (
    GROUP02_EXPIRED_NOTES,
    GROUP02_INVALID_CNPJ_NOTES,
    GROUP02_UNMAPPED_NOTES,
    GROUP02_VALID_NOTES,
)
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    LAB_TODAY,
    cnpj,
    company_name,
    group_rng,
    is_valid_cnpj,
    next_moment,
    previous_moment,
)


logger = logging.getLogger(__name__)

INDEXER_CODES = (
    ("SELIC", "IDX-SELIC", True),
    ("CDI", "IDX-CDI", True),
    ("IPCA", "IDX-IPCA", True),
    ("PREFIXADO", "IDX-PRE", True),
    ("IGPM", "IDX-IGPM", False),
)
UNMAPPED_INDEXERS = ("IPCA+", "CDI-LONGO", "SELIC-LINKED")


def _already_seeded(db: Session, model: type) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def _month_bucket(start: date, count: int) -> list[str]:
    months: list[str] = []
    current = start
    for _ in range(count):
        months.append(current.strftime("%Y-%m"))
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        current = date(year, month, 1)
    return months


def _rate_for(indexador: str, month_index: int, row_index: int) -> float:
    base = {
        "SELIC": 0.102,
        "CDI": 0.109,
        "IPCA": 0.057,
        "PREFIXADO": 0.121,
        "IGPM": 0.063,
    }.get(indexador, 0.135)
    return round(base + (month_index % 9) * 0.0025 + (row_index % 7) * 0.0009, 4)


def _maturity_for(month_label: str, row_index: int) -> str:
    year, month = (int(part) for part in month_label.split("-", maxsplit=1))
    origin = date(year, month, 15)
    delta_days = (-120, -30, 45, 120, 240, 420)[row_index % 6]
    return (origin + timedelta(days=delta_days)).isoformat()


def seed_group(db: Session) -> None:
    from ...models.labs.group02_rates import (
        IngestionFile,
        IndexerMapping,
        PrimaryMarketRate,
    )

    if _already_seeded(db, PrimaryMarketRate):
        logger.info("Group 02 already seeded")
        return

    rng = group_rng(2)
    months = _month_bucket(date(2024, 1, 1), 33)
    total_rows = LAB_MIN_RECORDS + 176
    total_files = 24
    rows_per_file = total_rows // total_files
    extra_rows = total_rows % total_files

    mappings = [
        IndexerMapping(
            mapping_id=f"MAP-{index + 1:03d}",
            indexador=indexador,
            codigo=codigo,
            ativo=ativo,
        )
        for index, (indexador, codigo, ativo) in enumerate(INDEXER_CODES)
    ]
    db.add_all(mappings)

    files: list[IngestionFile] = []
    rates: list[PrimaryMarketRate] = []
    global_index = 0

    for file_number in range(total_files):
        file_id = f"FILE-{file_number + 1:04d}"
        file_rows = rows_per_file + (1 if file_number < extra_rows else 0)
        file_created_at = previous_moment(rng, LAB_NOW, min_minutes=60, max_days=700)
        file_updated_at = next_moment(rng, file_created_at, min_minutes=10, max_days=6)
        rejected = file_number % 5 == 4
        invalid_count = 0

        file_rates: list[PrimaryMarketRate] = []
        for line_number in range(1, file_rows + 1):
            global_index += 1
            month_label = months[(global_index - 1) % len(months)]
            month_index = (global_index - 1) % len(months)
            invalid_row = rejected and line_number % 4 == 0
            mapped_indexer = INDEXER_CODES[(global_index - 1) % len(INDEXER_CODES)][0]
            indexador = (
                UNMAPPED_INDEXERS[(line_number // 4) % len(UNMAPPED_INDEXERS)]
                if invalid_row and line_number % 8 == 0
                else mapped_indexer
            )
            rate_created_at = max(
                file_created_at,
                previous_moment(rng, LAB_NOW, min_minutes=30, max_days=680),
            )
            rate_updated_at = next_moment(
                rng, rate_created_at, min_minutes=5, max_days=5
            )
            rate_cnpj = cnpj(rng, valid=not invalid_row)
            vencimento = _maturity_for(month_label, global_index)

            note_pool = GROUP02_VALID_NOTES
            if invalid_row:
                invalid_count += 1
                if indexador in UNMAPPED_INDEXERS:
                    note_pool = GROUP02_UNMAPPED_NOTES
                elif vencimento < LAB_TODAY.isoformat():
                    note_pool = GROUP02_EXPIRED_NOTES
                else:
                    note_pool = GROUP02_INVALID_CNPJ_NOTES
            elif vencimento < LAB_TODAY.isoformat() and line_number % 3 == 0:
                note_pool = GROUP02_EXPIRED_NOTES

            rate = PrimaryMarketRate(
                rate_id=f"RATE-{global_index:06d}",
                file_id=file_id,
                line_number=line_number,
                mes=month_label,
                indexador=indexador,
                cnpj=rate_cnpj,
                emissor=company_name(rng),
                taxa=_rate_for(indexador, month_index, global_index),
                vencimento=vencimento,
                status="INVALIDO" if invalid_row else "VALIDO",
                observacao=rng.choice(note_pool),
                created_at=rate_created_at,
                updated_at=rate_updated_at,
            )
            if invalid_row:
                assert not is_valid_cnpj(rate.cnpj)
            else:
                assert is_valid_cnpj(rate.cnpj)
            file_rates.append(rate)

        file_status = "REJECTED" if rejected else "PROCESSED"
        files.append(
            IngestionFile(
                file_id=file_id,
                nome_arquivo=f"mercado_primario_{file_number + 1:04d}.xlsx",
                origem=("tesouraria", "origem_b3", "mesa_credito")[file_number % 3],
                status=file_status,
                records_valid=file_rows - invalid_count,
                records_invalid=invalid_count,
                created_at=file_created_at,
                updated_at=file_updated_at,
            )
        )
        rates.extend(file_rates)

    db.add_all(files)
    db.flush()
    db.add_all(rates)
    db.commit()
    logger.info("Group 02 seeded with %d rates across %d files", len(rates), len(files))
