from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...services.audit_service import create_event


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
                {"email": "buyer@quantum.example", "amount": 42.5},
            ]
        }
    )


@router.get(
    "/api/v1/lab/slow",
    response_model=dict,
    tags=["Lab"],
    operation_id="lab_slow",
)
async def lab_slow(
    seconds: int = Query(default=5, ge=1, le=15),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, int | str]:
    _ = (x_lab_group, x_request_id)
    await asyncio.sleep(seconds)
    return {"message": f"Response after {seconds} seconds", "seconds": seconds}


@router.get(
    "/api/v1/lab/error",
    response_model=dict,
    tags=["Lab"],
    operation_id="lab_error",
    responses={500: {"description": "Simulated internal server error"}},
)
async def lab_error(
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _ = create_event(
        db,
        event_type="lab_error_triggered",
        lab_group=x_lab_group,
        resource_type="lab_failure",
        resource_id=x_request_id,
        metadata={"path": "/api/v1/lab/error"},
    )
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Simulated internal server error")


@router.get(
    "/api/v1/lab/rate-limit",
    response_model=dict,
    tags=["Lab"],
    operation_id="lab_rate_limit",
)
async def lab_rate_limit(
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
):
    _ = x_request_id
    now = time.time()
    recent_requests = [timestamp for timestamp in _rate_limit_tracker[x_lab_group] if now - timestamp < RATE_LIMIT_WINDOW_SECONDS]
    _rate_limit_tracker[x_lab_group] = recent_requests

    if len(recent_requests) >= RATE_LIMIT_MAX_REQUESTS:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests", "retry_after_seconds": RATE_LIMIT_RETRY_AFTER_SECONDS},
            headers={"Retry-After": str(RATE_LIMIT_RETRY_AFTER_SECONDS)},
        )

    _rate_limit_tracker[x_lab_group].append(now)
    return {
        "message": "Request accepted",
        "lab_group": x_lab_group,
        "requests_in_window": len(_rate_limit_tracker[x_lab_group]),
    }


@router.get(
    "/api/v1/lab/not-found",
    response_model=dict,
    tags=["Lab"],
    operation_id="lab_not_found",
    responses={404: {"description": "Resource not found (simulated)"}},
)
async def lab_not_found(
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, str]:
    _ = (x_lab_group, x_request_id)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found (simulated)")


@router.post(
    "/api/v1/lab/validation",
    response_model=dict,
    tags=["Lab"],
    operation_id="lab_validation",
)
async def lab_validation(
    payload: ValidationPayload,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, float | str]:
    _ = (x_lab_group, x_request_id)
    return {
        "message": "Validation passed",
        "email": payload.email,
        "amount": payload.amount,
    }
