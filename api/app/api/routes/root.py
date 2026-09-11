from fastapi import APIRouter, Header


router = APIRouter()


@router.get(
    "/",
    response_model=dict,
    tags=["Root"],
    operation_id="root",
    summary="Root endpoint",
    description="Return basic service entrypoint links for documentation, OpenAPI and health status.",
    responses={200: {"description": "Root metadata returned successfully"}},
)
async def root(
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, str]:
    _ = (x_student_id, x_request_id)
    return {
        "service": "FlowDesk Lab API",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
    }
