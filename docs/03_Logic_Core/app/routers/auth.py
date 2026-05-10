from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import authenticate_user, create_access_token, require_role
from app.database import get_db
from app.models import User, UserRole
from app.schemas import SessionRequest, Token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Exchange username/password credentials for a JWT access token."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        subject=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
    )
    return Token(access_token=access_token)


@router.post("/session", response_model=Token)
async def create_session(
    payload: SessionRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
) -> Token:
    """Create a short-lived auditor session token for a pharmacy contact."""
    access_token = create_access_token(
        subject=payload.contact_email,
        tenant_id=current_user.tenant_id,
        role=UserRole.AUDITOR,
        expires_delta=timedelta(hours=24),
        additional_claims={"pharmacy_name": payload.pharmacy_name},
    )
    return Token(access_token=access_token)
