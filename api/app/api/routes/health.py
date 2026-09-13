from fastapi import APIRouter


router = APIRouter()


def _health_payload() -> dict[str, str]:
    return {"status": "ok", "service": "quantum-commerce-api", "version": "2.0.0"}


@router.get(
    "/health",
    response_model=dict,
    tags=["Health"],
    operation_id="railway_health_check",
)
async def railway_health_check() -> dict[str, str]:
    return _health_payload()


@router.get(
    "/api/v1/health",
    response_model=dict,
    tags=["Health"],
    operation_id="health_check",
)
async def health_check() -> dict[str, str]:
    return _health_payload()
