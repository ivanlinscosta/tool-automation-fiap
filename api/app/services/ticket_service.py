from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed import TEAMS
from app.models.priority import PriorityRequest
from app.models.ticket import Ticket, TicketCreate, TicketFilter
from app.services.priority_service import calculate_priority


def _generate_ticket_id(db: Session) -> str:
    existing_ids = db.execute(select(Ticket.ticket_id)).scalars().all()
    max_number = max((int(ticket_id.split("-")[-1]) for ticket_id in existing_ids), default=1000)
    return f"TK-{max_number + 1}"


def _resolve_team(category: str) -> dict[str, str | int]:
    normalized_category = category.strip().lower()
    return TEAMS.get(normalized_category, TEAMS["other"])


def create_ticket(db: Session, payload: TicketCreate, student_id: str) -> Ticket:
    priority_result = calculate_priority(
        PriorityRequest(
            employee_id=payload.employee_id,
            category=payload.category,
            impact=payload.impact,
            urgency=payload.urgency,
        )
    )
    team_config = _resolve_team(payload.category)

    ticket = Ticket(
        ticket_id=_generate_ticket_id(db),
        status="open",
        employee_id=payload.employee_id,
        category=team_config["category"],
        priority=priority_result.priority,
        assigned_team=team_config["team"],
        queue=team_config["queue"],
        summary=payload.summary,
        description=payload.description,
        source=payload.source,
        student_id=student_id,
        created_at=datetime.utcnow(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_ticket_by_id(db: Session, ticket_id: str) -> Ticket | None:
    return db.get(Ticket, ticket_id)


def get_ticket(db: Session, ticket_id: str) -> Ticket | None:
    return get_ticket_by_id(db, ticket_id)


def list_tickets(db: Session, filters: TicketFilter | None = None) -> list[Ticket]:
    query = select(Ticket)

    if filters:
        if filters.employee_id:
            query = query.where(Ticket.employee_id == filters.employee_id)
        if filters.category:
            query = query.where(Ticket.category == filters.category.strip().lower())
        if filters.priority:
            query = query.where(Ticket.priority == filters.priority)
        if filters.status:
            query = query.where(Ticket.status == filters.status)

    query = query.order_by(Ticket.created_at.desc())
    return list(db.execute(query).scalars().all())
