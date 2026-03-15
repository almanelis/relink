from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str | None = Depends(oauth2_scheme)
) -> User | None:
    if not token:
        return None
    email = decode_access_token(token)
    if not email:
        return None
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
