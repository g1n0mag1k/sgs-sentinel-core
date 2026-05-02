from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional
from uuid import UUID

class ScoreRequest(BaseModel):
    """Payload for DSCSA risk assessment."""
    payload: dict[str, Any] = Field(..., description="EPCIS JSON data")

class ScoreResponse(BaseModel):
    """Assessment score returned by the DSCSA scoring service."""
    score: int = Field(ge=0, le=100)
    risk_tier: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")

class TenantResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    
    class Config:
        from_attributes = True