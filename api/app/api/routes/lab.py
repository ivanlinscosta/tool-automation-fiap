from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field


router = APIRouter()

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 3
RATE_LIMIT_RETRY_AFTER_SECONDS = 10
_rate_limit_tracker: dict[str, list[float]] = defaultdict(list)


class ValidationPayload(BaseModel):
    email: EmailStr
    amount: float = Field(..., ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"email": "student@flowdesk.lab", "amount": 42.5},
            ]
        }
    )


@router.get(
    "/api/v1/lab/slow",
    response_model=dict,
    tags=["Lab - Failure Scenarios"],
    operation_id="lab_slow",
    summary="Slow response simulation",
    description="Sleep for the requested number of seconds and then return a delayed success response.",
    responses={200: {"description": "Delayed response returned successfully"}},
)
async def lab_slow(
    seconds: int = Query(default=5, ge=1, le=15),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, int | str]:
    _ = (x_student_id, x_request_id)
    await asyncio.sleep(seconds)
    return {"message": f"Response after {seconds} seconds", "seconds": seconds}


@router.get(
    "/api/v1/lab/error",
    response_model=dict,
    tags=["Lab - Failure Scenarios"],
    operation_id="lab_error",
    summary="Internal server error simulation",
    description="Always raises an HTTP 500 error to simulate an internal server failure.",
    responses={500: {"description": "Simulated internal server error"}},
)
async def lab_error(
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, str]:
    _ = (x_student_id, x_request_id)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Simulated internal server error",
    )


@router.get(
    "/api/v1/lab/rate-limit",
    response_model=dict,
    tags=["Lab - Failure Scenarios"],
    operation_id="lab_rate_limit",
    summary="Rate limit simulation",
    description="Applies a simple in-memory rate limit of three requests per student within sixty seconds.",
    responses={
        200: {"description": "Request accepted within rate limit"},
        429: {
            "description": "Too many requests",
            "headers": {
                "Retry-After": {
                    "description": "Number of seconds to wait before retrying.",
                    "schema": {"type": "integer", "example": 10},
                }
            },
        },
    },
)
async def lab_rate_limit(
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, int | str]:
    _ = x_request_id
    now = time.time()
    recent_requests = [
        timestamp
        for timestamp in _rate_limit_tracker[x_student_id]
        if now - timestamp < RATE_LIMIT_WINDOW_SECONDS
    ]
    _rate_limit_tracker[x_student_id] = recent_requests

    if len(recent_requests) >= RATE_LIMIT_MAX_REQUESTS:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Too many requests",
                "retry_after_seconds": RATE_LIMIT_RETRY_AFTER_SECONDS,
            },
            headers={"Retry-After": str(RATE_LIMIT_RETRY_AFTER_SECONDS)},
        )

    _rate_limit_tracker[x_student_id].append(now)
    return {
        "message": "Request accepted",
        "student_id": x_student_id,
        "requests_in_window": len(_rate_limit_tracker[x_student_id]),
    }


@router.get(
    "/api/v1/lab/not-found",
    response_model=dict,
    tags=["Lab - Failure Scenarios"],
    operation_id="lab_not_found",
    summary="Not found simulation",
    description="Always raises an HTTP 404 error to simulate a missing resource.",
    responses={404: {"description": "Resource not found (simulated)"}},
)
async def lab_not_found(
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, str]:
    _ = (x_student_id, x_request_id)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Resource not found (simulated)",
    )


@router.post(
    "/api/v1/lab/validation",
    response_model=dict,
    tags=["Lab - Failure Scenarios"],
    operation_id="lab_validation",
    summary="Validation error simulation",
    description="Validate an email and non-negative amount payload, producing FastAPI validation errors when the schema is invalid.",
    responses={
        200: {"description": "Validation passed"},
        422: {"description": "Validation error"},
    },
)
async def lab_validation(
    payload: ValidationPayload,
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, float | str]:
    _ = (x_student_id, x_request_id)
    return {
        "message": "Validation passed",
        "email": payload.email,
        "amount": payload.amount,
    }
