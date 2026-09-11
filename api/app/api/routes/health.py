from fastapi import APIRouter, Header


router = APIRouter()


@router.get(
    "/health",
    response_model=dict,
    tags=["Health"],
    operation_id="health_check",
    summary="Health check endpoint",
    description="Returns service health status. Used by Railway for healthchecks.",
    responses={200: {"description": "Service is healthy"}},
)
async def health_check(
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> dict[str, str]:
    _ = (x_student_id, x_request_id)
    return {"status": "ok", "service": "fiap-student-desk-lab-api", "version": "1.0.0"}
