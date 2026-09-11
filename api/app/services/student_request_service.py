from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.seed import DEPARTMENTS
from ..models.student_request import StudentRequest, StudentRequestCreate, StudentRequestFilter, StudentRequestUpdate


def _next_request_number(db: Session) -> int:
    existing_ids = db.execute(select(StudentRequest.request_id)).scalars().all()
    max_number = max((int(request_id.split("-")[-1]) for request_id in existing_ids), default=1000)
    return max_number + 1


def _resolve_department(category: str) -> tuple[str, dict[str, str | int | bool]]:
    normalized_category = category.strip().lower()
    department = DEPARTMENTS.get(normalized_category, DEPARTMENTS["other"])
    resolved_category = normalized_category if normalized_category in DEPARTMENTS else "other"
    return resolved_category, department


def _resolve_department_assignment(assigned_department: str) -> tuple[str, str | None]:
    normalized_value = assigned_department.strip().lower()
    if normalized_value in DEPARTMENTS:
        department = DEPARTMENTS[normalized_value]
        return str(department["department_name"]), str(department["queue"])

    for department in DEPARTMENTS.values():
        department_name = str(department["department_name"])
        if department_name.strip().lower() == normalized_value:
            return str(department["department_name"]), str(department["queue"])

    return assigned_department.strip(), None


def create_request(db: Session, payload: StudentRequestCreate, lab_student_id: str) -> StudentRequest:
    request_number = _next_request_number(db)
    resolved_category, department = _resolve_department(payload.category)

    student_request = StudentRequest(
        request_id=f"REQ-{request_number}",
        protocol=f"FIAP-LAB-REQ-{request_number:04d}",
        status="open",
        student_id=payload.student_id,
        category=resolved_category,
        priority=payload.priority.strip().lower(),
        assigned_department=str(department["department_name"]),
        queue=str(department["queue"]),
        summary=payload.summary,
        description=payload.description,
        source=payload.source,
        lab_student_id=lab_student_id,
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    db.add(student_request)
    db.commit()
    db.refresh(student_request)
    return student_request


def get_request(db: Session, request_id: str) -> StudentRequest | None:
    return db.get(StudentRequest, request_id)


def list_requests(db: Session, filters: StudentRequestFilter | None) -> list[StudentRequest]:
    query = select(StudentRequest)
    if filters:
        if filters.student_id:
            query = query.where(StudentRequest.student_id == filters.student_id)
        if filters.category:
            query = query.where(StudentRequest.category == filters.category.strip().lower())
        if filters.priority:
            query = query.where(StudentRequest.priority == filters.priority.strip().lower())
        if filters.status:
            query = query.where(StudentRequest.status == filters.status)
    query = query.order_by(StudentRequest.created_at.desc())
    return list(db.execute(query).scalars().all())


def update_request(db: Session, request_id: str, update: StudentRequestUpdate) -> StudentRequest | None:
    student_request = db.get(StudentRequest, request_id)
    if student_request is None:
        return None

    changed = False

    if update.status is not None:
        student_request.status = update.status
        changed = True

    if update.priority is not None:
        student_request.priority = update.priority.strip().lower()
        changed = True

    if update.assigned_department is not None:
        assigned_department, queue = _resolve_department_assignment(update.assigned_department)
        student_request.assigned_department = assigned_department
        if queue is not None:
            student_request.queue = queue
        changed = True

    if changed:
        student_request.updated_at = datetime.now(UTC)
        db.add(student_request)
        db.commit()
        db.refresh(student_request)

    return student_request
