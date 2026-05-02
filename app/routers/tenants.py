from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Tenant, User, UserRole
from app.schemas import TenantCreate, TenantResponse

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[TenantResponse]:
    """List all tenants. Admin only."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    return list(result.scalars().all())


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> TenantResponse:
    """Create a new tenant. Admin only."""
    tenant = Tenant(name=payload.name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantResponse:
    """Retrieve a single tenant by ID."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    # Non-admin users may only view their own tenant
    if current_user.role != UserRole.ADMIN and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return tenant
