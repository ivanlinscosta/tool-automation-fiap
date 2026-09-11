from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.seed import get_department, list_departments
from ...models.department import DepartmentResponse
from ...services.audit_service import create_event


router = APIRouter()


@router.get(
    "/api/v1/departments",
    response_model=list[DepartmentResponse],
    response_model_by_alias=False,
    tags=["Departments"],
    operation_id="list_departments",
    summary="List departments",
    description="List all FIAP Student Desk Lab departments from seed data.",
)
async def list_departments_route(
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> list[DepartmentResponse]:
    departments = [DepartmentResponse.model_validate(department) for department in list_departments()]
    _ = create_event(
        db=db,
        event_type="department_queried",
        student_id=x_student_id,
        fictional_student_id=None,
        resource_type="department",
        resource_id="all",
        metadata={"request_id": x_request_id, "count": len(departments), "action": "list"},
    )
    return departments


@router.get(
    "/api/v1/departments/{category}",
    response_model=DepartmentResponse,
    response_model_by_alias=False,
    tags=["Departments"],
    operation_id="get_department",
    summary="Get department by category",
    description="Retrieve a department by category key, such as academic_services or campus_access.",
    responses={404: {"description": "Department not found"}},
)
async def get_department_route(
    category: str = Path(..., examples=["academic_services"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> DepartmentResponse:
    department = get_department(category)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    _ = create_event(
        db=db,
        event_type="department_queried",
        student_id=x_student_id,
        fictional_student_id=None,
        resource_type="department",
        resource_id=str(department["category"]),
        metadata={"request_id": x_request_id, "action": "get"},
    )
    return DepartmentResponse.model_validate(department)
