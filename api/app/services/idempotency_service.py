from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.idempotency import IdempotencyKey


class IdempotencyConflictError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def get_replay(db: Session, key: str, lab_group: str) -> IdempotencyKey | None:
    return db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.lab_group == lab_group,
        )
    ).scalar_one_or_none()


def replay_or_none(db: Session, key: str, lab_group: str, resource_type: str) -> IdempotencyKey | None:
    """
    Idempotency-Key resolution contract:
    - no stored row -> None (caller creates the resource, then calls mark_applied)
    - stored row, same resource_type -> returns it (caller returns the existing resource with HTTP 200)
    - stored row, different resource_type -> raises IdempotencyConflictError (HTTP 409)
    """
    row = get_replay(db, key, lab_group)
    if row is None:
        return None
    if row.resource_type != resource_type:
        raise IdempotencyConflictError(
            f"Idempotency-Key '{key}' was already used for {row.resource_type} {row.resource_id} "
            f"and cannot be reused for {resource_type}"
        )
    return row


def mark_applied(db: Session, key: str, lab_group: str, resource_type: str, resource_id: str) -> IdempotencyKey:
    row = IdempotencyKey(
        key=key,
        lab_group=lab_group,
        resource_type=resource_type,
        resource_id=resource_id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
