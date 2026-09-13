from fastapi import APIRouter


router = APIRouter()


@router.get(
    "/",
    response_model=dict,
    tags=["Root"],
    operation_id="root",
)
async def root() -> dict[str, str]:
    return {
        "service": "Quantum Commerce API",
        "version": "2.0.0",
        "docs": "/docs",
        "api_base": "/api/v1",
    }
