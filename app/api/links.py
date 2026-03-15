from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_user
from app.db.session import get_db
from app.models.expired_link import ExpiredLink
from app.models.link import Link
from app.models.user import User
from app.schemas.link import (
    LinkCreateRequest,
    LinkResponse,
    LinkStatsResponse,
    LinkUpdateRequest,
)
from app.services.cache import cache_delete, cache_get, cache_set
from app.services.shortener import generate_short_code
from app.tasks.cleanup import cleanup_links

router = APIRouter(prefix="/links", tags=["links"])


async def _resolve_unique_code(
    db: AsyncSession, custom_alias: str | None = None, attempts: int = 10
) -> str:
    if custom_alias:
        existing = await db.execute(select(Link).where(Link.short_code == custom_alias))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Alias already exists")
        return custom_alias

    for _ in range(attempts):
        code = generate_short_code()
        existing = await db.execute(select(Link).where(Link.short_code == code))
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique short code")


async def _get_link_or_404(db: AsyncSession, short_code: str) -> Link:
    result = await db.execute(select(Link).where(Link.short_code == short_code))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    return link


def _link_to_response(link: Link) -> LinkResponse:
    return LinkResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
        owner_id=link.owner_id,
    )


@router.post("/shorten", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def create_short_link(
    payload: LinkCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
) -> LinkResponse:
    await cleanup_links(db)
    short_code = await _resolve_unique_code(db, payload.custom_alias)
    link = Link(
        short_code=short_code,
        original_url=str(payload.original_url),
        expires_at=payload.expires_at,
        owner_id=user.id if user else None,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _link_to_response(link)


@router.get("/search", response_model=list[LinkResponse])
async def search_by_original_url(
    original_url: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[LinkResponse]:
    await cleanup_links(db)
    result = await db.execute(select(Link).where(Link.original_url == original_url))
    links = result.scalars().all()
    return [_link_to_response(link) for link in links]


@router.get("/expired/history")
async def expired_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(ExpiredLink).order_by(desc(ExpiredLink.removed_at)).limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "short_code": item.short_code,
            "original_url": item.original_url,
            "created_at": item.created_at,
            "removed_at": item.removed_at,
            "click_count": item.click_count,
            "owner_id": item.owner_id,
            "reason": item.reason,
        }
        for item in records
    ]


@router.get("/{short_code}")
async def redirect_to_original(short_code: str, db: AsyncSession = Depends(get_db)) -> Response:
    await cleanup_links(db)

    cached = await cache_get(f"redirect:{short_code}")
    if cached:
        # Even with cache hit we still count transition in DB.
        result = await db.execute(select(Link).where(Link.short_code == short_code))
        link = result.scalar_one_or_none()
        if link is None:
            await cache_delete(f"redirect:{short_code}")
            raise HTTPException(status_code=404, detail="Short link not found")
    else:
        link = await _get_link_or_404(db, short_code)
        await cache_set(f"redirect:{short_code}", {"url": link.original_url})

    link.click_count += 1
    link.last_accessed_at = datetime.now(UTC)
    await db.commit()
    await cache_delete(f"stats:{short_code}")
    return RedirectResponse(url=link.original_url, status_code=307)


@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> Response:
    link = await _get_link_or_404(db, short_code)
    if link.owner_id is not None and link.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if link.owner_id is None:
        raise HTTPException(
            status_code=403,
            detail="Anonymous links cannot be managed by authenticated users",
        )

    await db.delete(link)
    await db.commit()
    await cache_delete(f"stats:{short_code}", f"redirect:{short_code}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{short_code}", response_model=LinkResponse)
async def update_link(
    short_code: str,
    payload: LinkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> LinkResponse:
    link = await _get_link_or_404(db, short_code)
    if link.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    link.original_url = str(payload.original_url)
    await db.commit()
    await db.refresh(link)
    await cache_delete(f"stats:{short_code}", f"redirect:{short_code}")
    return _link_to_response(link)


@router.get("/{short_code}/stats", response_model=LinkStatsResponse)
async def get_link_stats(short_code: str, db: AsyncSession = Depends(get_db)) -> LinkStatsResponse:
    await cleanup_links(db)
    cache_key = f"stats:{short_code}"
    cached = await cache_get(cache_key)
    if cached:
        return LinkStatsResponse(**cached)

    link = await _get_link_or_404(db, short_code)
    stats = LinkStatsResponse(
        short_code=link.short_code,
        original_url=link.original_url,
        created_at=link.created_at,
        click_count=link.click_count,
        last_accessed_at=link.last_accessed_at,
        expires_at=link.expires_at,
    )
    await cache_set(cache_key, stats.model_dump(mode="json"))
    return stats
