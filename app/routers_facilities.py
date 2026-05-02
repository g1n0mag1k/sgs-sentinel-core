from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.database import get_db
from app.models import Facility, UserRole
from app.schemas import FacilityCreate, FacilityResponse

router = APIRouter(prefix="/api/tenants", tags=["facilities"])

_admin_or_manager = require_role(UserRole.ADMIN, UserRole.MANAGER)


@router.post(
    "/{tenant_id}/facilities",
    response_model=FacilityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin_or_manager],
)
async def create_facility(
    tenant_id: UUID,
    body: FacilityCreate,
    db: AsyncSession = Depends(get_db),
) -> FacilityResponse:
    facility = Facility(tenant_id=tenant_id, name=body.name, gln=body.gln)
    db.add(facility)
    await db.commit()
    await db.refresh(facility)
    return facility


@router.get(
    "/{tenant_id}/facilities",
    response_model=list[FacilityResponse],
    dependencies=[_admin_or_manager],
)
async def list_facilities(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[FacilityResponse]:
    result = await db.execute(
        select(Facility).where(Facility.tenant_id == tenant_id)
    )
    return result.scalars().all()
