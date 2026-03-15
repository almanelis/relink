from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.expired_link import ExpiredLink
from app.models.link import Link
from app.services.cache import cache_delete

settings = get_settings()


async def _archive_link(session: AsyncSession, link: Link, reason: str) -> None:
    session.add(
        ExpiredLink(
            short_code=link.short_code,
            original_url=link.original_url,
            created_at=link.created_at,
            click_count=link.click_count,
            owner_id=link.owner_id,
            reason=reason,
        )
    )
    await cache_delete(f"stats:{link.short_code}", f"redirect:{link.short_code}")
    await session.delete(link)


async def cleanup_links(session: AsyncSession) -> int:
    now = datetime.now(UTC)
    inactive_threshold = now - timedelta(days=settings.inactive_days)

    result = await session.execute(
        select(Link).where(
            or_(
                Link.expires_at.is_not(None) & (Link.expires_at <= now),
                func.coalesce(Link.last_accessed_at, Link.created_at) <= inactive_threshold,
            )
        )
    )
    links = result.scalars().all()

    removed = 0
    for link in links:
        reason = "expired"
        if link.expires_at is None or link.expires_at > now:
            reason = "inactive"
        await _archive_link(session, link, reason)
        removed += 1

    if removed:
        await session.commit()
    return removed
