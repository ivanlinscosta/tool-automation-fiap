from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.seed import get_student, list_students
from ...models.student import StudentResponse
from ...services.audit_service import create_event


router = APIRouter()


@router.get(
    "/api/v1/students",
    response_model=list[StudentResponse],
    tags=["Students"],
    operation_id="list_students",
    summary="List fictional students",
    description="List all fictional FIAP Student Desk Lab students from seed data.",
)
async def list_students_route(
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> list[StudentResponse]:
    students = [StudentResponse.model_validate(student) for student in list_students()]
    _ = create_event(
        db=db,
        event_type="student_queried",
        student_id=x_student_id,
        fictional_student_id=None,
        resource_type="student",
        resource_id="all",
        metadata={"request_id": x_request_id, "count": len(students), "action": "list"},
    )
    return students


@router.get(
    "/api/v1/students/{student_id}",
    response_model=StudentResponse,
    tags=["Students"],
    operation_id="get_student",
    summary="Get fictional student by ID",
    description="Retrieve a fictional student by ID, such as STU001.",
    responses={404: {"description": "Student not found"}},
)
async def get_student_route(
    student_id: str = Path(..., examples=["STU001"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> StudentResponse:
    student = get_student(student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    _ = create_event(
        db=db,
        event_type="student_queried",
        student_id=x_student_id,
        fictional_student_id=str(student["id"]),
        resource_type="student",
        resource_id=str(student["id"]),
        metadata={"request_id": x_request_id, "action": "get"},
    )
    return StudentResponse.model_validate(student)
