from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.employee import Employee, EmployeeResponse


router = APIRouter()


def _find_employee(db: Session, employee_id: str) -> Employee | None:
    try:
        employee = db.get(Employee, employee_id)
        if employee is not None:
            return employee
    except Exception:
        pass

    query = getattr(db, "query", None)
    if query is None:
        return None

    for attr_name in ("employee_id", "id", "code"):
        model_attr = getattr(Employee, attr_name, None)
        if model_attr is None:
            continue
        try:
            employee = query(Employee).filter(model_attr == employee_id).first()
        except Exception:
            continue
        if employee is not None:
            return employee

    return None


@router.get(
    "/api/v1/employees/{employee_id}",
    response_model=EmployeeResponse,
    tags=["Employees"],
    operation_id="get_employee",
    summary="Get employee by ID",
    description="Retrieve employee details by their unique ID (e.g., EMP001)",
    responses={
        200: {"description": "Employee retrieved successfully"},
        404: {"description": "Employee not found"},
    },
)
async def get_employee(
    employee_id: str = Path(..., examples=["EMP001"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> EmployeeResponse:
    _ = (x_student_id, x_request_id)
    employee = _find_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee
