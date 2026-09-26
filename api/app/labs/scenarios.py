import asyncio
import logging

from fastapi import HTTPException, status

from ..config import settings


logger = logging.getLogger(__name__)

SCENARIOS = (
    "success",
    "validation_error",
    "not_found",
    "duplicate",
    "timeout",
    "server_error",
)

SCENARIO_DESCRIPTIONS: dict[str, str] = {
    "success": "Executes the endpoint normally and returns the real mock payload.",
    "validation_error": "Returns HTTP 422 describing a simulated payload rejection.",
    "not_found": "Returns HTTP 404 as if the upstream record did not exist.",
    "duplicate": "Returns HTTP 409 as if the resource had already been processed.",
    "timeout": "Sleeps for LABS_SCENARIO_TIMEOUT_SECONDS then returns HTTP 504.",
    "server_error": "Returns HTTP 500 as if the upstream dependency failed.",
}


def scenario_error_response(scenario: str) -> HTTPException | None:
    if scenario == "validation_error":
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Simulated validation error: field 'mensagem' failed the upstream contract",
        )
    if scenario == "not_found":
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulated not found: upstream resource does not exist",
        )
    if scenario == "duplicate":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulated duplicate: resource was already processed for this idempotency key",
        )
    if scenario == "server_error":
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Simulated server error: upstream dependency failed",
        )
    return None


async def apply_scenario(scenario: str | None) -> None:
    if scenario is None or scenario == "success":
        return

    if not settings.LABS_ALLOW_SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario simulation is disabled on this environment (LABS_ALLOW_SCENARIOS=false)",
        )

    if scenario == "timeout":
        await asyncio.sleep(settings.LABS_SCENARIO_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "Simulated timeout: no response from upstream after "
                f"{settings.LABS_SCENARIO_TIMEOUT_SECONDS}s"
            ),
        )

    error = scenario_error_response(scenario)
    if error is not None:
        raise error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown scenario '{scenario}'. Supported values: {', '.join(SCENARIOS)}",
    )


def scenario_availability() -> dict[str, object]:
    return {
        "enabled": settings.LABS_ALLOW_SCENARIOS,
        "supported_scenarios": list(SCENARIOS),
        "descriptions": SCENARIO_DESCRIPTIONS,
        "timeout_seconds": settings.LABS_SCENARIO_TIMEOUT_SECONDS,
    }


def scenario_docs() -> str:
    return (
        "Controlled failure injection for teaching error handling. "
        "Use ?scenario=success|validation_error|not_found|duplicate|timeout|server_error. "
        "Applies to lab endpoints only and never to the production modules."
    )
