from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models.policy import Policy
from ...services.audit_service import create_event


router = APIRouter()


def _serialize_policy(policy: Policy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "category": policy.category,
        "title": policy.title,
        "country": policy.country,
        "content": policy.content,
        "effective_from": policy.effective_from,
    }


@router.get(
    "/api/v1/policies",
    response_model=list[dict[str, Any]],
    tags=["Policies"],
    operation_id="list_policies",
)
async def list_policies_route(
    category: str | None = Query(default=None),
    country: str | None = Query(default=None),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(Policy)
    if category:
        query = query.where(Policy.category == category)
    if country:
        query = query.where(Policy.country == country)

    policies = list(db.execute(query.order_by(Policy.id)).scalars().all())
    _ = create_event(
        db=db,
        event_type="policy_searched",
        lab_group=x_lab_group,
        resource_type="policy",
        resource_id="list",
        metadata={"category": category, "country": country, "results": len(policies)},
    )
    return [_serialize_policy(policy) for policy in policies]


@router.get(
    "/api/v1/policies/search",
    response_model=list[dict[str, Any]],
    tags=["Policies"],
    operation_id="search_policies",
)
async def search_policies_route(
    q: str = Query(...),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    policies = list(
        db.execute(
            select(Policy)
            .where(or_(Policy.title.ilike(f"%{q}%"), Policy.content.ilike(f"%{q}%")))
            .order_by(Policy.id)
        )
        .scalars()
        .all()
    )
    _ = create_event(
        db=db,
        event_type="policy_searched",
        lab_group=x_lab_group,
        resource_type="policy",
        resource_id="search",
        metadata={"q": q, "results": len(policies)},
    )
    return [_serialize_policy(policy) for policy in policies]


@router.get(
    "/api/v1/policies/{policy_id}",
    response_model=dict[str, Any],
    tags=["Policies"],
    operation_id="get_policy",
)
async def get_policy_route(
    policy_id: str = Path(...),
    x_lab_group: str = Header(default="anonymous", alias="X-Lab-Group"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    policy = db.execute(select(Policy).where(Policy.id == policy_id)).scalar_one_or_none()
    _ = create_event(
        db=db,
        event_type="policy_searched",
        lab_group=x_lab_group,
        resource_type="policy",
        resource_id=policy_id,
        metadata={"found": policy is not None},
    )
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return _serialize_policy(policy)
