from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.interaction import Interaction, InteractionCreate, InteractionDetail, InteractionResponse
from ...services.audit_service import create_event


router = APIRouter()


def _next_interaction_id(db: Session) -> str:
    max_number = 0
    interaction_ids = db.execute(select(Interaction.interaction_id)).scalars().all()
    for interaction_id in interaction_ids:
        try:
            max_number = max(max_number, int(interaction_id.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"INT-{max_number + 1}"


@router.post(
    "/api/v1/interactions",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Interactions"],
    operation_id="create_interaction",
)
async def create_interaction_route(
    payload: InteractionCreate,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> InteractionResponse:
    interaction = Interaction(
        interaction_id=_next_interaction_id(db),
        customer_id=payload.customer_id,
        channel=payload.channel,
        message=payload.message,
        response=payload.response,
        source=payload.source,
        lab_group=x_lab_group,
        created_at=datetime.now(UTC),
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    _ = create_event(
        db=db,
        event_type="interaction_created",
        lab_group=x_lab_group,
        resource_type="interaction",
        resource_id=interaction.interaction_id,
        metadata={"channel": interaction.channel, "source": interaction.source},
        customer_id=interaction.customer_id,
    )

    return InteractionResponse.model_validate(interaction)


@router.get(
    "/api/v1/interactions",
    response_model=list[InteractionDetail],
    tags=["Interactions"],
    operation_id="list_interactions",
)
async def list_interactions_route(
    customer_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[InteractionDetail]:
    query = select(Interaction)
    if customer_id:
        query = query.where(Interaction.customer_id == customer_id)
    if x_lab_group != "anonymous":
        query = query.where(Interaction.lab_group == x_lab_group)

    interactions = list(
        db.execute(query.order_by(Interaction.created_at.desc(), Interaction.interaction_id.desc()).limit(limit)).scalars().all()
    )

    _ = create_event(
        db=db,
        event_type="interaction_created",
        lab_group=x_lab_group,
        resource_type="interaction",
        resource_id="list",
        metadata={"customer_id": customer_id, "limit": limit, "result_count": len(interactions)},
        customer_id=customer_id,
    )

    return [InteractionDetail.model_validate(interaction) for interaction in interactions]


@router.get(
    "/api/v1/interactions/{interaction_id}",
    response_model=InteractionDetail,
    tags=["Interactions"],
    operation_id="get_interaction",
    responses={404: {"description": "Interaction not found"}},
)
async def get_interaction_route(
    interaction_id: str,
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> InteractionDetail:
    interaction = db.execute(
        select(Interaction).where(Interaction.interaction_id == interaction_id)
    ).scalar_one_or_none()
    if interaction is None or (x_lab_group != "anonymous" and interaction.lab_group != x_lab_group):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found")
    return InteractionDetail.model_validate(interaction)
