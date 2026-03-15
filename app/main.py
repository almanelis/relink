import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import router as auth_router
from app.api.links import router as links_router, redirect_to_original
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.services.cache import close_cache, init_cache
from app.tasks.cleanup import cleanup_links

settings = get_settings()
cleanup_task: asyncio.Task | None = None


async def cleanup_worker() -> None:
    while True:
        async with SessionLocal() as session:
            await cleanup_links(session)
        await asyncio.sleep(settings.cleanup_interval_sec)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global cleanup_task
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await init_cache()
    cleanup_task = asyncio.create_task(cleanup_worker())

    yield

    if cleanup_task is not None:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    await close_cache()
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(auth_router)
app.include_router(links_router)


@app.get("/health", tags=["service"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/{short_code}", include_in_schema=False)
async def root_redirect(short_code: str, db: AsyncSession = Depends(get_db)):
    return await redirect_to_original(short_code, db)
