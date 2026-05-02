from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, settings
from app.models import User, UserRole

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def create_access_token(
    subject: str,
    tenant_id: UUID,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    """Mint a signed JWT containing user identity and tenant context."""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,          # user email
        "tenant_id": str(tenant_id),
        "role": role.value,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Decode JWT and return the authenticated User row."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exc

    return user


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

def require_role(*roles: UserRole):
    """Dependency factory — enforces that the current user holds one of the given roles.

    Returns a callable suitable for use with ``Depends``.

    Usage::

        # As a route parameter dependency:
        current_user: User = Depends(require_role(UserRole.ADMIN))

        # As a route-level dependency:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {[r.value for r in roles]}",
            )
        return user
    return _check


# ---------------------------------------------------------------------------
# Authenticate helper (used by login route)
# ---------------------------------------------------------------------------

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Return User if credentials are valid, None otherwise."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
