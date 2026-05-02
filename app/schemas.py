from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import UserRole


# ---------------------------------------------------------------------------
# DSCSA Assessment
# ---------------------------------------------------------------------------

class ScoreRequest(BaseModel):
    """Payload for DSCSA risk assessment."""
    payload: dict[str, Any] = Field(..., description="EPCIS JSON data")


class ScoreResponse(BaseModel):
    """Assessment score returned by the DSCSA scoring service."""
    score: int = Field(ge=0, le=100)
    risk_tier: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------

class TenantCreate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Facility
# ---------------------------------------------------------------------------

class FacilityCreate(BaseModel):
    name: str
    gln: str

    @field_validator("gln")
    @classmethod
    def validate_gln(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 13:
            raise ValueError("GLN must be exactly 13 numeric digits")
        return v


class FacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    gln: str
    created_at: datetime


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Auth / JWT
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: str | None = None
    tenant_id: str | None = None
    role: str | None = None