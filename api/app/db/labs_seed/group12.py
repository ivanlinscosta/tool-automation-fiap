import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...labs.artifacts import build_model_binary, sha256_hex
from ...labs.corpus_group12 import FRAMEWORKS, MODEL_LIMITATIONS, MODEL_SUMMARIES
from ...labs.generators import (
    LAB_MIN_RECORDS,
    LAB_NOW,
    group_rng,
    next_moment,
    previous_moment,
)


logger = logging.getLogger(__name__)


def _already_seeded(db: Session, model) -> bool:
    return db.execute(select(func.count()).select_from(model)).scalar_one() > 0


def _validation_rows(
    submission, artifact, card, metrics_rows, schema_rows, checked_at: object
):
    artifact_bytes = build_model_binary(
        artifact.id, submission.modelo_id, submission.version, artifact.size_bytes
    )
    checksum_ok = sha256_hex(artifact_bytes) == artifact.sha256
    yield (
        "CHECKSUM",
        "PASS" if checksum_ok else "FAIL",
        "Checksum confere com o artefato armazenado."
        if checksum_ok
        else "SHA256 divergente do binario recomputado.",
    )

    schema_ok = all(
        (row.dtype in {"int", "float", "string", "bool"}) and (not row.nullable)
        for row in schema_rows
    )
    yield (
        "SCHEMA",
        "PASS" if schema_ok else "FAIL",
        "Schema aderente ao contrato esperado."
        if schema_ok
        else "Schema contem nullable=True ou dtype inesperado.",
    )

    card_ok = card.completeness >= 60
    yield (
        "MODEL_CARD",
        "PASS" if card_ok else "FAIL",
        "Model card com completude suficiente."
        if card_ok
        else "Model card abaixo de 60 pontos de completude.",
    )

    metrics_ok = all(
        row.metric_value >= row.threshold
        for row in metrics_rows
        if row.metric_name in {"auc", "f1", "precision", "recall"}
    )
    yield (
        "METRICS",
        "PASS" if metrics_ok else "FAIL",
        "Metricas acima dos thresholds minimos."
        if metrics_ok
        else "Uma ou mais metricas ficaram abaixo do threshold.",
    )

    compliance_ok = submission.data_classificacao != "RESTRITO" or bool(
        card.approved_by
    )
    yield (
        "COMPLIANCE",
        "PASS" if compliance_ok else "FAIL",
        "Aprovacao de compliance registrada."
        if compliance_ok
        else "Modelo RESTRITO sem aprovacao de compliance.",
    )

    psi_row = next(row for row in metrics_rows if row.metric_name == "psi")
    bias_status = (
        "PASS"
        if psi_row.metric_value <= 0.2
        else "WARNING"
        if psi_row.metric_value <= 0.25
        else "FAIL"
    )
    detail = (
        "Indicador de estabilidade dentro do esperado."
        if bias_status == "PASS"
        else "PSI em zona de atencao."
        if bias_status == "WARNING"
        else "PSI acima do limite permitido."
    )
    yield ("BIAS", bias_status, detail)


def seed_group(db: Session) -> None:
    from ...models.labs.group12_models import (
        Deployment,
        FeatureSchema,
        JiraTicket,
        Metrics,
        ModelArtifact,
        ModelCard,
        ModelNotification,
        ModelSubmission,
        ValidationResult,
    )

    if _already_seeded(db, ModelSubmission):
        logger.info("Group 12 already seeded")
        return

    rng = group_rng(12)
    total = LAB_MIN_RECORDS + 16
    submissions: list[ModelSubmission] = []
    artifacts: list[ModelArtifact] = []
    metrics_rows: list[Metrics] = []
    schema_rows: list[FeatureSchema] = []
    cards: list[ModelCard] = []
    validations: list[ValidationResult] = []
    deployments: list[Deployment] = []
    jira_rows: list[JiraTicket] = []
    notifications: list[ModelNotification] = []

    for index in range(total):
        number = index + 1
        submitted_at = previous_moment(rng, LAB_NOW, min_minutes=240, max_days=220)
        submission = ModelSubmission(
            submission_id=f"SUB-{number:06d}",
            modelo_id=f"mdl-{number:06d}",
            nome_modelo=f"Modelo {number:06d}",
            version=f"{1 + number % 3}.{number % 10}.{number % 7}",
            owner=f"team-{number % 12}",
            framework=FRAMEWORKS[index % len(FRAMEWORKS)],
            submitted_at=submitted_at,
            status="DEPLOYADO"
            if number % 11 == 0
            else "APROVADO"
            if number % 7 == 0
            else "SUBMETIDO",
            target_env=("PROD", "STAGING", "DEV")[index % 3],
            data_classificacao=("PUBLICO", "INTERNO", "CONFIDENCIAL", "RESTRITO")[
                index % 4
            ],
        )
        submissions.append(submission)

        artifact_id = f"ART-{number:06d}"
        size_bytes = 256 + (number % 5) * 128
        payload = build_model_binary(
            artifact_id, submission.modelo_id, submission.version, size_bytes
        )
        sha_value = sha256_hex(payload)
        if number % 13 == 0:
            sha_value = sha_value[:-1] + ("0" if sha_value[-1] != "0" else "1")
        artifact = ModelArtifact(
            id=artifact_id,
            submission_id=submission.submission_id,
            filename=f"{submission.modelo_id}-{submission.version}.bin",
            content_type="application/octet-stream",
            size_bytes=size_bytes,
            sha256=sha_value,
            storage_path=f"/artifacts/{artifact_id}.bin",
            uploaded_at=next_moment(rng, submitted_at, min_minutes=5, max_days=2),
        )
        artifacts.append(artifact)

        metric_specs = {
            "auc": (0.91 if number % 8 else 0.63, 0.70),
            "f1": (0.82 if number % 9 else 0.58, 0.65),
            "precision": (0.84 if number % 10 else 0.60, 0.65),
            "recall": (0.80 if number % 12 else 0.59, 0.65),
            "psi": (0.09 if number % 6 else 0.27, 0.20),
        }
        current_metric_rows: list[Metrics] = []
        for metric_name, (metric_value, threshold) in metric_specs.items():
            row = Metrics(
                id=f"MET-{number:06d}-{metric_name}",
                submission_id=submission.submission_id,
                metric_name=metric_name,
                metric_value=metric_value,
                dataset="validation",
                evaluated_at=next_moment(rng, submitted_at, min_minutes=15, max_days=6),
                threshold=threshold,
            )
            metrics_rows.append(row)
            current_metric_rows.append(row)

        current_schema_rows: list[FeatureSchema] = []
        for feature_index, feature_name in enumerate(
            ("idade", "renda", "tempo_relacionamento")
        ):
            row = FeatureSchema(
                id=f"SCH-{number:06d}-{feature_index + 1}",
                submission_id=submission.submission_id,
                feature_name=feature_name,
                dtype="desconhecido"
                if number % 17 == 0 and feature_index == 0
                else ("int" if feature_index != 1 else "float"),
                nullable=number % 14 == 0 and feature_index == 2,
                min_value=0.0,
                max_value=100000.0,
                examples="[1, 2, 3]",
            )
            schema_rows.append(row)
            current_schema_rows.append(row)

        card = ModelCard(
            id=f"CRD-{number:06d}",
            model_id=submission.modelo_id,
            summary=MODEL_SUMMARIES[index % len(MODEL_SUMMARIES)],
            intended_use="Suporte a priorizacao operacional.",
            limitations=MODEL_LIMITATIONS[index % len(MODEL_LIMITATIONS)],
            ethical_considerations=(
                "Monitorar comportamento por segmento e drift temporal."
            ),
            license="interna",
            approved_by=None
            if submission.data_classificacao == "RESTRITO" and number % 5 == 0
            else "compliance.ml",
            approved_at=next_moment(rng, submitted_at, min_minutes=30, max_days=10),
            completeness=48 if number % 15 == 0 else 88,
        )
        cards.append(card)

        checked_at = next_moment(rng, submitted_at, min_minutes=40, max_days=12)
        status_by_check = list(
            _validation_rows(
                submission,
                artifact,
                card,
                current_metric_rows,
                current_schema_rows,
                checked_at,
            )
        )
        for check_name, check_status, detail in status_by_check:
            validations.append(
                ValidationResult(
                    id=f"VAL-{number:06d}-{check_name}",
                    submission_id=submission.submission_id,
                    check_name=check_name,
                    status=check_status,
                    detail=detail,
                    checked_at=checked_at,
                )
            )

        if submission.status == "DEPLOYADO":
            deployment_time = next_moment(rng, checked_at, min_minutes=60, max_days=15)
            deployments.append(
                Deployment(
                    id=f"DEP-{number:06d}",
                    model_id=submission.modelo_id,
                    environment=submission.target_env,
                    deployed_at=deployment_time,
                    status="CONCLUIDO",
                    replicas=2 + number % 3,
                    endpoint=f"https://ml.example/{submission.modelo_id}",
                )
            )
            jira_rows.append(
                JiraTicket(
                    id=f"JIR-{number:06d}",
                    submission_id=submission.submission_id,
                    key=f"ML-{2000 + number}",
                    summary=f"Deploy {submission.modelo_id} em {submission.target_env}",
                    status="RESOLVIDO",
                    created_at=deployment_time,
                )
            )
            notifications.append(
                ModelNotification(
                    id=f"NTF-{number:06d}",
                    submission_id=submission.submission_id,
                    destino=submission.owner,
                    canal="email",
                    mensagem=(
                        f"Deploy do modelo {submission.modelo_id} concluido em "
                        f"{submission.target_env}."
                    ),
                    enviado_em=deployment_time,
                    lida=number % 2 == 0,
                )
            )

    db.add_all(submissions)
    db.add_all(artifacts)
    db.add_all(metrics_rows)
    db.add_all(schema_rows)
    db.add_all(cards)
    db.add_all(validations)
    db.add_all(deployments)
    db.add_all(jira_rows)
    db.add_all(notifications)
    db.commit()
    logger.info("Group 12 seeded with %d submissions", len(submissions))
