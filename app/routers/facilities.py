from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Facility, User, UserRole
from app.schemas import FacilityCreate, FacilityResponse

router = APIRouter(prefix="/api/v1/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityResponse])
async def list_facilities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FacilityResponse]:
    """List all facilities belonging to the current user's tenant."""
    result = await db.execute(
        select(Facility)
        .where(Facility.tenant_id == current_user.tenant_id)
        .order_by(Facility.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
async def create_facility(
    payload: FacilityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(UserRole.ADMIN, UserRole.MANAGER),
) -> FacilityResponse:
    """Create a new facility under the current user's tenant."""
    facility = Facility(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        gln=payload.gln,
    )
    db.add(facility)
    await db.commit()
    await db.refresh(facility)
    return facility


@router.get("/{facility_id}", response_model=FacilityResponse)
async def get_facility(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FacilityResponse:
    """Retrieve a single facility by ID, scoped to the current user's tenant."""
    result = await db.execute(
        select(Facility).where(
            Facility.id == facility_id,
            Facility.tenant_id == current_user.tenant_id,
        )
    )
    facility = result.scalar_one_or_none()
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    return facility


@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_facility(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = require_role(UserRole.ADMIN, UserRole.MANAGER),
) -> None:
    """Delete a facility by ID, scoped to the current user's tenant."""
    result = await db.execute(
        select(Facility).where(
            Facility.id == facility_id,
            Facility.tenant_id == current_user.tenant_id,
        )
    )
    facility = result.scalar_one_or_none()
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    await db.delete(facility)
    await db.commit()
