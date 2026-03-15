from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.expired_link import ExpiredLink
from app.models.link import Link
from app.tasks.cleanup import cleanup_links


@pytest.mark.asyncio
async def test_cleanup_moves_expired_and_inactive_links(db_session):
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Link(
                short_code="expired1",
                original_url="https://expired.example",
                created_at=now - timedelta(days=2),
                expires_at=now - timedelta(minutes=1),
                click_count=2,
                owner_id=7,
            ),
            Link(
                short_code="inactive1",
                original_url="https://inactive.example",
                created_at=now - timedelta(days=45),
                expires_at=None,
                click_count=0,
                owner_id=None,
            ),
            Link(
                short_code="alive1",
                original_url="https://alive.example",
                created_at=now,
                expires_at=now + timedelta(days=3),
                click_count=1,
                owner_id=3,
            ),
        ]
    )
    await db_session.commit()

    removed = await cleanup_links(db_session)
    assert removed == 2

    links_after = await db_session.execute(select(Link))
    short_codes = {row.short_code for row in links_after.scalars().all()}
    assert short_codes == {"alive1"}

    archived = await db_session.execute(select(ExpiredLink))
    archived_rows = archived.scalars().all()
    reasons = {item.short_code: item.reason for item in archived_rows}
    assert reasons["expired1"] == "expired"
    assert reasons["inactive1"] == "inactive"


@pytest.mark.asyncio
async def test_cleanup_returns_zero_when_nothing_to_remove(db_session):
    db_session.add(
        Link(
            short_code="fresh",
            original_url="https://fresh.example",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=1),
            click_count=0,
            owner_id=None,
        )
    )
    await db_session.commit()

    removed = await cleanup_links(db_session)
    assert removed == 0
