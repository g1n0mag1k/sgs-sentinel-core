from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.database import get_db
from app.models import Tenant, UserRole
from app.schemas import TenantCreate, TenantResponse

router = APIRouter(prefix="/api/tenants", tags=["tenants"])

_admin = require_role(UserRole.ADMIN)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[_admin])
async def create_tenant(
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    tenant = Tenant(name=body.name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse, dependencies=[_admin])
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant
