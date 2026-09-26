import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.labs.group12_models import (
    Deployment,
    FeatureSchema,
    Metrics,
    ModelArtifact,
    ModelCard,
    ModelSubmission,
    ValidationResult,
)


LAB_GROUP = "test-labs-12"
BASE = "/api/v1/labs/groups"


def _headers(**extra: str) -> dict[str, str]:
    return {"X-Lab-Group": LAB_GROUP, **extra}


@pytest.fixture(autouse=True)
def _instructor_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LABS_INSTRUCTOR_KEY", "chave-de-instrutor")


def _submission_payload(
    modelo_id: str,
    *,
    restricted: bool = False,
    complete: int = 92,
    auc: float = 0.91,
    nullable: bool = False,
    approved_by: str | None = "compliance.ml",
) -> dict:
    return {
        "modelo_id": modelo_id,
        "nome_modelo": "Fraud Scorer",
        "version": "1.0.0",
        "owner": "time-risco",
        "framework": "xgboost",
        "target_env": "PROD",
        "data_classificacao": "RESTRITO" if restricted else "INTERNO",
        "artifact_size_bytes": 512,
        "metrics": {
            "auc": auc,
            "f1": 0.83,
            "precision": 0.84,
            "recall": 0.82,
            "psi": 0.11,
        },
        "feature_schema": [
            {
                "feature_name": "idade",
                "dtype": "int",
                "nullable": False,
                "min_value": 18,
                "max_value": 90,
                "examples": "[25, 41]",
            },
            {
                "feature_name": "renda",
                "dtype": "float",
                "nullable": nullable,
                "min_value": 0,
                "max_value": 50000,
                "examples": "[3200.5, 4500.0]",
            },
        ],
        "model_card": {
            "summary": "Modelo",
            "intended_use": "Triagem",
            "limitations": "Nao usar sozinho",
            "ethical_considerations": "Monitorar vies",
            "license": "interna",
            "approved_by": approved_by,
            "completeness": complete,
        },
    }


def _list_submissions(client: TestClient, **params: object) -> dict:
    response = client.get(f"{BASE}/12/submissions", params=params, headers=_headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_group12_seeds_at_least_one_thousand_submissions(client: TestClient) -> None:
    assert _list_submissions(client, limit=1)["meta"]["total"] >= 1000


def test_group12_filters_sorting_and_invalid_sort(client: TestClient) -> None:
    filtered = _list_submissions(
        client, framework="xgboost", limit=20, sort="submission_id"
    )
    assert all(item["framework"] == "xgboost" for item in filtered["items"])
    invalid = client.get(
        f"{BASE}/12/submissions", params={"sort": "nao_existe"}, headers=_headers()
    )
    assert invalid.status_code == 400


def test_group12_validation_failures_and_deploy_gate(
    client: TestClient, db_session: Session
) -> None:
    created = client.post(
        f"{BASE}/12/submissions",
        json=_submission_payload(
            "mdl-test-fail",
            restricted=True,
            complete=40,
            auc=0.60,
            nullable=True,
            approved_by=None,
        ),
        headers=_headers(),
    )
    assert created.status_code == 201, created.text
    submission_id = created.json()["submission_id"]
    artifact = db_session.execute(
        select(ModelArtifact)
        .where(ModelArtifact.submission_id == submission_id)
        .limit(1)
    ).scalar_one()
    artifact.sha256 = "0" * 64
    db_session.commit()

    validated = client.post(
        f"{BASE}/12/submissions/{submission_id}/validate", headers=_headers()
    )
    assert validated.status_code == 200, validated.text
    check_map = {
        item["check_name"]: item["status"] for item in validated.json()["checks"]
    }
    assert check_map["CHECKSUM"] == "FAIL"
    assert check_map["SCHEMA"] == "FAIL"
    assert check_map["MODEL_CARD"] == "FAIL"
    assert check_map["METRICS"] == "FAIL"
    assert check_map["COMPLIANCE"] == "FAIL"

    approve = client.post(
        f"{BASE}/12/submissions/{submission_id}/approve", headers=_headers()
    )
    deploy = client.post(
        f"{BASE}/12/submissions/{submission_id}/deploy", headers=_headers()
    )
    assert approve.status_code == 409
    assert deploy.status_code == 409


def test_group12_happy_path_validate_approve_deploy_and_rollback(
    client: TestClient,
) -> None:
    created = client.post(
        f"{BASE}/12/submissions",
        json=_submission_payload("mdl-test-pass"),
        headers=_headers(),
    )
    assert created.status_code == 201, created.text
    submission_id = created.json()["submission_id"]
    validated = client.post(
        f"{BASE}/12/submissions/{submission_id}/validate", headers=_headers()
    )
    assert validated.status_code == 200
    assert validated.json()["overall_status"] in {"PASS", "WARNING"}
    approved = client.post(
        f"{BASE}/12/submissions/{submission_id}/approve", headers=_headers()
    )
    assert approved.status_code == 200
    deployed = client.post(
        f"{BASE}/12/submissions/{submission_id}/deploy", headers=_headers()
    )
    assert deployed.status_code == 200, deployed.text
    rolled = client.post(
        f"{BASE}/12/deployments/{deployed.json()['id']}/rollback", headers=_headers()
    )
    assert rolled.status_code == 200
    assert rolled.json()["status"] == "ROLLBACK"


def test_group12_artifact_and_documents_are_deterministic(
    client: TestClient, db_session: Session
) -> None:
    submission_id = _list_submissions(client, limit=1)["items"][0]["submission_id"]
    artifact = db_session.execute(
        select(ModelArtifact)
        .where(ModelArtifact.submission_id == submission_id)
        .limit(1)
    ).scalar_one()
    first = client.get(
        f"{BASE}/12/submissions/{submission_id}/artifacts/{artifact.id}/download",
        headers=_headers(),
    )
    second = client.get(
        f"{BASE}/12/submissions/{submission_id}/artifacts/{artifact.id}/download",
        headers=_headers(),
    )
    card = client.get(
        f"{BASE}/12/submissions/{submission_id}/model-card", headers=_headers()
    )
    schema = client.get(
        f"{BASE}/12/submissions/{submission_id}/feature-schema", headers=_headers()
    )
    metrics = client.get(
        f"{BASE}/12/submissions/{submission_id}/metrics", headers=_headers()
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.content == second.content
    assert hashlib.sha256(first.content).hexdigest() == artifact.sha256
    assert (
        card.status_code == 200
        and schema.status_code == 200
        and metrics.status_code == 200
    )


def test_group12_temporal_coherence_and_integrity(
    client: TestClient, db_session: Session
) -> None:
    submissions = {
        row.submission_id: row
        for row in db_session.execute(select(ModelSubmission)).scalars().all()
    }
    model_ids = {row.modelo_id for row in submissions.values()}
    for row in db_session.execute(select(ModelArtifact)).scalars().all():
        assert row.submission_id in submissions
        assert submissions[row.submission_id].submitted_at <= row.uploaded_at
    for row in db_session.execute(select(Metrics)).scalars().all():
        assert row.submission_id in submissions
        assert submissions[row.submission_id].submitted_at <= row.evaluated_at
    for row in db_session.execute(select(FeatureSchema)).scalars().all():
        assert row.submission_id in submissions
    for row in db_session.execute(select(ModelCard)).scalars().all():
        assert row.model_id in model_ids
    for row in db_session.execute(select(ValidationResult)).scalars().all():
        assert row.submission_id in submissions
        assert submissions[row.submission_id].submitted_at <= row.checked_at
    for row in db_session.execute(select(Deployment)).scalars().all():
        assert row.model_id in model_ids
    integrity = client.get(
        "/api/v1/labs/groups/12/integrity",
        headers=_headers(**{"X-Instructor-Key": "chave-de-instrutor"}),
    )
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["healthy"] is True


def test_group12_determinism_across_reset(client: TestClient) -> None:
    first = _list_submissions(client, limit=100)["items"]
    reset = client.post(
        "/api/v1/labs/reset",
        json={"groups": [12]},
        headers=_headers(**{"X-Instructor-Key": "chave-de-instrutor"}),
    )
    assert reset.status_code == 200, reset.text
    second = _list_submissions(client, limit=100)["items"]
    assert first == second


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("validation_error", 422),
        ("not_found", 404),
        ("duplicate", 409),
        ("server_error", 500),
    ],
)
def test_group12_scenarios_on_read_and_write(
    client: TestClient, scenario: str, expected: int
) -> None:
    read_response = client.get(
        f"{BASE}/12/submissions", params={"scenario": scenario}, headers=_headers()
    )
    assert read_response.status_code == expected
    submission_id = _list_submissions(client, limit=1)["items"][0]["submission_id"]
    write_response = client.post(
        f"{BASE}/12/submissions/{submission_id}/validate",
        params={"scenario": scenario},
        headers=_headers(),
    )
    assert write_response.status_code == expected


def test_group12_timeout_and_missing_entity(client: TestClient) -> None:
    timeout = client.get(
        f"{BASE}/12/submissions", params={"scenario": "timeout"}, headers=_headers()
    )
    missing = client.get(f"{BASE}/12/submissions/SUB-999999", headers=_headers())
    stats = client.get(f"{BASE}/12/model-stats", headers=_headers())
    assert timeout.status_code == 504
    assert missing.status_code == 404
    assert stats.status_code == 200
