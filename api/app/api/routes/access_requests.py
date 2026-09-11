from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.access_request import AccessRequest, AccessRequestApproval, AccessRequestCreate, AccessRequestResponse
from app.services.access_service import approve_access_request, create_access_request, get_access_request


router = APIRouter()


async def _call_service(function: Any, fallback_args: list[tuple[Any, ...]], **kwargs: Any) -> Any:
    try:
        signature = inspect.signature(function)
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        supported_kwargs = (
            kwargs
            if accepts_kwargs
            else {key: value for key, value in kwargs.items() if key in signature.parameters}
        )
        if supported_kwargs:
            result = function(**supported_kwargs)
        else:
            raise TypeError("No matching keyword arguments")
    except TypeError:
        last_error: TypeError | None = None
        for args in fallback_args:
            try:
                result = function(*args)
                break
            except TypeError as exc:
                last_error = exc
        else:
            if last_error is not None:
                raise last_error
            raise

    if inspect.isawaitable(result):
        return await result
    return result


@router.post(
    "/api/v1/access-requests",
    response_model=AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Access Requests"],
    operation_id="create_access_request",
    summary="Create access request",
    description="Create a new access request for a system or resource.",
    responses={
        201: {"description": "Access request created successfully"},
        422: {"description": "Validation error"},
    },
)
async def create_access_request_route(
    access_request_data: AccessRequestCreate = Body(
        ...,
        openapi_examples={
            "vpn_access": {
                "summary": "VPN access request",
                "value": {
                    "employee_id": "EMP001",
                    "resource": "Corporate VPN",
                    "justification": "Needs secure remote access for on-call support.",
                    "risk": "high",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> AccessRequestResponse:
    created_request = await _call_service(
        create_access_request,
        fallback_args=[
            (access_request_data, db, x_student_id, x_request_id),
            (db, access_request_data, x_student_id, x_request_id),
            (access_request_data, db),
            (db, access_request_data),
            (access_request_data,),
        ],
        db=db,
        access_request=access_request_data,
        access_request_data=access_request_data,
        payload=access_request_data,
        student_id=x_student_id,
        request_id=x_request_id,
    )
    return created_request


@router.get(
    "/api/v1/access-requests/{request_id}",
    response_model=AccessRequestResponse,
    tags=["Access Requests"],
    operation_id="get_access_request",
    summary="Get access request by ID",
    description="Retrieve an access request by its unique identifier.",
    responses={
        200: {"description": "Access request retrieved successfully"},
        404: {"description": "Access request not found"},
    },
)
async def get_access_request_route(
    request_id: str = Path(..., examples=["AR-501"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> AccessRequestResponse:
    access_request = await _call_service(
        get_access_request,
        fallback_args=[
            (request_id, db, x_student_id, x_request_id),
            (request_id, db, x_student_id),
            (request_id, db),
            (request_id,),
        ],
        db=db,
        request_id=request_id,
        id=request_id,
        student_id=x_student_id,
        request_header_id=x_request_id,
    )
    if access_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found")
    return access_request


@router.post(
    "/api/v1/access-requests/{request_id}/approve",
    response_model=AccessRequestResponse,
    tags=["Access Requests"],
    operation_id="approve_access_request",
    summary="Approve access request",
    description="Approve or reject an access request.",
    responses={
        200: {"description": "Access request processed successfully"},
        404: {"description": "Access request not found"},
        422: {"description": "Validation error"},
    },
)
async def approve_access_request_route(
    request_id: str = Path(..., examples=["AR-501"]),
    approval: AccessRequestApproval = Body(
        ...,
        openapi_examples={
            "approved": {
                "summary": "Approve with approver note",
                "value": {
                    "decision": "approved",
                    "approved_by": "professor@fiap.com.br",
                    "decision_comment": "Approved for demonstration in classroom.",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> AccessRequestResponse:
    updated_request = await _call_service(
        approve_access_request,
        fallback_args=[
            (request_id, approval, db, x_student_id, x_request_id),
            (request_id, db, approval, x_student_id, x_request_id),
            (request_id, approval, db),
            (request_id, db, approval),
            (request_id, approval),
        ],
        db=db,
        request_id=request_id,
        id=request_id,
        approval=approval,
        approval_data=approval,
        payload=approval,
        student_id=x_student_id,
        request_header_id=x_request_id,
        request_id_header=x_request_id,
    )
    if updated_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found")
    return updated_request
