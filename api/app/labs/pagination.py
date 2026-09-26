import math
from typing import Any

from fastapi import HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def page_params(
    limit: int = Query(default=20, ge=1, le=200, description="Maximum number of records to return."),
    offset: int = Query(default=0, ge=0, description="Number of records to skip before returning results."),
) -> tuple[int, int]:
    return limit, offset


def build_page(
    db: Session,
    query: Select,
    limit: int,
    offset: int,
    serializer: Any = None,
) -> dict[str, Any]:
    total = int(db.execute(select(func.count()).select_from(query.subquery())).scalar_one())
    rows = list(db.execute(query.limit(limit).offset(offset)).scalars().all())
    return {
        "items": [serializer(row) for row in rows] if serializer else rows,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "total_pages": math.ceil(total / limit) if limit else 0,
            "has_more": offset + len(rows) < total,
        },
    }


def apply_sort(query: Select, model: type, sort: str | None, order: str | None) -> Select:
    if not sort:
        return query
    column = getattr(model, sort, None)
    if column is None or not hasattr(column, "asc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort field '{sort}'",
        )
    descending = (order or "asc").lower() == "desc"
    return query.order_by(column.desc() if descending else column.asc())
