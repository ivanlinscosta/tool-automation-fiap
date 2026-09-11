from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.seed import get_student
from ...models.student_request import StudentRequestCreate, StudentRequestFilter, StudentRequestResponse, StudentRequestUpdate
from ...services.audit_service import create_event
from ...services.student_request_service import create_request, get_request, list_requests, update_request


router = APIRouter()


@router.post(
    "/api/v1/requests",
    response_model=StudentRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Requests"],
    operation_id="create_request",
    summary="Create student request",
    description="Create a new FIAP Student Desk Lab academic request.",
)
async def create_request_route(
    request_data: StudentRequestCreate = Body(
        ...,
        openapi_examples={
            "declaration_request": {
                "summary": "Enrollment declaration request",
                "value": {
                    "student_id": "STU001",
                    "category": "academic_services",
                    "priority": "medium",
                    "summary": "Need enrollment declaration for internship process",
                    "description": "Fictional request to obtain a didactic enrollment declaration for a lab workflow.",
                    "source": "api",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> StudentRequestResponse:
    if get_student(request_data.student_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    created_request = create_request(db=db, payload=request_data, lab_student_id=x_student_id)
    _ = create_event(
        db=db,
        event_type="request_created",
        student_id=x_student_id,
        fictional_student_id=created_request.student_id,
        resource_type="student_request",
        resource_id=created_request.request_id,
        metadata={
            "request_id": x_request_id,
            "protocol": created_request.protocol,
            "category": created_request.category,
            "priority": created_request.priority,
        },
    )
    return created_request


@router.get(
    "/api/v1/requests",
    response_model=list[StudentRequestResponse],
    tags=["Requests"],
    operation_id="list_requests",
    summary="List student requests",
    description="List student requests with optional filters and lab-group isolation by X-Student-ID.",
)
async def list_requests_route(
    student_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    request_status: str | None = Query(default=None, alias="status"),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> list[StudentRequestResponse]:
    _ = x_request_id
    filters = StudentRequestFilter(student_id=student_id, category=category, priority=priority, status=request_status)
    return [request for request in list_requests(db=db, filters=filters) if request.lab_student_id == x_student_id]


@router.get(
    "/api/v1/requests/{request_id}",
    response_model=StudentRequestResponse,
    tags=["Requests"],
    operation_id="get_request",
    summary="Get request by ID",
    description="Retrieve a student request by ID.",
    responses={404: {"description": "Request not found"}},
)
async def get_request_route(
    request_id: str = Path(..., examples=["REQ-1001"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> StudentRequestResponse:
    _ = x_request_id
    request_item = get_request(db=db, request_id=request_id)
    if request_item is None or request_item.lab_student_id != x_student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request_item


@router.patch(
    "/api/v1/requests/{request_id}",
    response_model=StudentRequestResponse,
    tags=["Requests"],
    operation_id="update_request",
    summary="Update request",
    description="Update request status, priority, or assigned department.",
    responses={404: {"description": "Request not found"}},
)
async def update_request_route(
    request_id: str = Path(..., examples=["REQ-1001"]),
    update_data: StudentRequestUpdate = Body(...),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> StudentRequestResponse:
    existing_request = get_request(db=db, request_id=request_id)
    if existing_request is None or existing_request.lab_student_id != x_student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    updated_request = update_request(db=db, request_id=request_id, update=update_data)
    if updated_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    _ = create_event(
        db=db,
        event_type="request_updated",
        student_id=x_student_id,
        fictional_student_id=updated_request.student_id,
        resource_type="student_request",
        resource_id=updated_request.request_id,
        metadata={
            "request_id": x_request_id,
            "status": updated_request.status,
            "priority": updated_request.priority,
            "assigned_department": updated_request.assigned_department,
        },
    )
    return updated_request
