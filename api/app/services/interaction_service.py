import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.interaction import Interaction, InteractionCreate


def _next_interaction_number(db: Session) -> int:
    existing_ids = db.execute(select(Interaction.interaction_id)).scalars().all()
    max_number = max((int(interaction_id.split("-")[-1]) for interaction_id in existing_ids), default=1000)
    return max_number + 1


def create_interaction(db: Session, payload: InteractionCreate, lab_student_id: str) -> Interaction:
    interaction = Interaction(
        interaction_id=f"INT-{_next_interaction_number(db):04d}",
        student_id=payload.student_id,
        request_text=payload.request_text,
        category=payload.category.strip().lower(),
        response_type=payload.response_type,
        response_text=payload.response_text,
        knowledge_articles=json.dumps(payload.knowledge_articles, ensure_ascii=False),
        source=payload.source,
        lab_student_id=lab_student_id,
        created_at=datetime.now(UTC),
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


def get_interaction(db: Session, interaction_id: str) -> Interaction | None:
    return db.get(Interaction, interaction_id)


def list_interactions(db: Session, student_id: str | None = None) -> list[Interaction]:
    query = select(Interaction)
    if student_id:
        query = query.where(Interaction.student_id == student_id)
    query = query.order_by(Interaction.created_at.desc())
    return list(db.execute(query).scalars().all())
