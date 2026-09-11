import json

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.seed import get_student
from ...models.interaction import Interaction, InteractionCreate, InteractionResponse
from ...services.audit_service import create_event
from ...services.interaction_service import create_interaction, get_interaction, list_interactions


router = APIRouter()


def _serialize_interaction(interaction: Interaction) -> InteractionResponse:
    return InteractionResponse(
        interaction_id=interaction.interaction_id,
        student_id=interaction.student_id,
        request_text=interaction.request_text,
        category=interaction.category,
        response_type=interaction.response_type,
        response_text=interaction.response_text,
        knowledge_articles=json.loads(interaction.knowledge_articles),
        source=interaction.source,
        lab_student_id=interaction.lab_student_id,
        created_at=interaction.created_at,
    )


@router.post(
    "/api/v1/interactions",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Interactions"],
    operation_id="create_interaction",
    summary="Create interaction record",
    description="Store an interaction between a fictional student and the student desk lab.",
)
async def create_interaction_route(
    interaction_data: InteractionCreate = Body(
        ...,
        openapi_examples={
            "automatic_answer": {
                "summary": "Automatic answer based on knowledge base",
                "value": {
                    "student_id": "STU001",
                    "request_text": "Como acesso o ambiente digital de aprendizagem?",
                    "category": "digital_learning",
                    "response_type": "automatic",
                    "response_text": "Use o passo a passo didático do artigo KB001.",
                    "knowledge_articles": ["KB001"],
                    "source": "api",
                },
            }
        },
    ),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> InteractionResponse:
    if get_student(interaction_data.student_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    interaction = create_interaction(db=db, payload=interaction_data, lab_student_id=x_student_id)
    if interaction.response_type.strip().lower() == "automatic":
        _ = create_event(
            db=db,
            event_type="automatic_answer_generated",
            student_id=x_student_id,
            fictional_student_id=interaction.student_id,
            resource_type="interaction",
            resource_id=interaction.interaction_id,
            metadata={"request_id": x_request_id, "knowledge_articles": json.loads(interaction.knowledge_articles)},
        )
    return _serialize_interaction(interaction)


@router.get(
    "/api/v1/interactions",
    response_model=list[InteractionResponse],
    tags=["Interactions"],
    operation_id="list_interactions",
    summary="List interactions",
    description="List stored interactions, optionally filtered by fictional student ID.",
)
async def list_interactions_route(
    student_id: str | None = Query(default=None),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> list[InteractionResponse]:
    _ = x_request_id
    return [_serialize_interaction(item) for item in list_interactions(db=db, student_id=student_id) if item.lab_student_id == x_student_id]


@router.get(
    "/api/v1/interactions/{interaction_id}",
    response_model=InteractionResponse,
    tags=["Interactions"],
    operation_id="get_interaction",
    summary="Get interaction by ID",
    description="Retrieve an interaction by ID.",
    responses={404: {"description": "Interaction not found"}},
)
async def get_interaction_route(
    interaction_id: str = Path(..., examples=["INT-1001"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> InteractionResponse:
    _ = x_request_id
    interaction = get_interaction(db=db, interaction_id=interaction_id)
    if interaction is None or interaction.lab_student_id != x_student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found")
    return _serialize_interaction(interaction)
