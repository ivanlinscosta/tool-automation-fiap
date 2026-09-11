from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.seed import KNOWLEDGE_ARTICLES, get_knowledge_article, list_knowledge_articles
from ...models.knowledge import KnowledgeArticleResponse, KnowledgeSearchResponse, KnowledgeSearchResult
from ...services.audit_service import create_event
from ...services.knowledge_service import get_article, search_knowledge


router = APIRouter()


@router.get(
    "/api/v1/knowledge",
    response_model=list[KnowledgeArticleResponse],
    tags=["Knowledge"],
    operation_id="list_knowledge_articles",
    summary="List knowledge articles",
    description="List all knowledge base articles with optional category filtering.",
)
async def list_knowledge_route(
    category: str | None = Query(default=None),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> list[KnowledgeArticleResponse]:
    _ = (x_student_id, x_request_id)
    return [KnowledgeArticleResponse.model_validate(article) for article in list_knowledge_articles(category)]


@router.get(
    "/api/v1/knowledge/search",
    response_model=KnowledgeSearchResponse,
    tags=["Knowledge"],
    operation_id="search_knowledge",
    summary="Search knowledge base",
    description="Search the knowledge base using keyword overlap, optionally boosting a chosen category.",
)
async def search_knowledge_route(
    q: str = Query(..., min_length=1),
    category: str | None = Query(default=None),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
    db: Session = Depends(get_db),
) -> KnowledgeSearchResponse:
    results = search_knowledge(query=q, category=category, articles=KNOWLEDGE_ARTICLES)
    _ = create_event(
        db=db,
        event_type="knowledge_searched",
        student_id=x_student_id,
        fictional_student_id=None,
        resource_type="knowledge_search",
        resource_id=x_request_id,
        metadata={"query": q, "category": category, "result_count": len(results)},
    )

    if results and results[0].get("can_answer_automatically") and not results[0].get("requires_human"):
        _ = create_event(
            db=db,
            event_type="automatic_answer_generated",
            student_id=x_student_id,
            fictional_student_id=None,
            resource_type="knowledge_article",
            resource_id=str(results[0]["id"]),
            metadata={"query": q, "score": results[0]["score"]},
        )

    return KnowledgeSearchResponse(
        query=q,
        results=[KnowledgeSearchResult(**{key: result[key] for key in ("id", "title", "category", "score", "content")}) for result in results],
    )


@router.get(
    "/api/v1/knowledge/{article_id}",
    response_model=KnowledgeArticleResponse,
    tags=["Knowledge"],
    operation_id="get_knowledge_article",
    summary="Get knowledge article by ID",
    description="Retrieve a knowledge article by ID, such as KB001.",
    responses={404: {"description": "Knowledge article not found"}},
)
async def get_knowledge_route(
    article_id: str = Path(..., examples=["KB001"]),
    x_student_id: str = Header(default="anonymous", alias="X-Student-ID"),
    x_request_id: str = Header(default="anonymous", alias="X-Request-ID"),
) -> KnowledgeArticleResponse:
    _ = (x_student_id, x_request_id)
    article = get_article(article_id, KNOWLEDGE_ARTICLES) or get_knowledge_article(article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge article not found")
    return KnowledgeArticleResponse.model_validate(article)
