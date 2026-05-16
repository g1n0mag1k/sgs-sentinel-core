from typing import Literal, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

AttestationAnswer = Literal["yes", "partial", "no"]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ScoreRequest(BaseModel):
    """Request for DSCSA risk scoring."""
    payload: dict[str, Any]

class ScoreResponse(BaseModel):
    """Response with technical score and flags."""
    score: int = Field(ge=0, le=100)
    risk_tier: Literal["LOW", "MEDIUM", "HIGH"]
    flags: list[str] = Field(default_factory=list)

class M1M6Attestation(BaseModel):
    answers: dict[str, AttestationAnswer]
    # e.g. {"M1-Q1": "yes", "M2-Q3": "partial", ...}
    submitted_glns: list[str] = Field(default_factory=list)

class DualScoreRequest(BaseModel):
    epcis_payload: dict[str, Any]
    attestation: M1M6Attestation
    facility_name: str
    profile: str | None = "manufacturer"  # Profile type; defaults to "manufacturer"
    attestor_name: str | None = None
    attestor_title: str | None = None
    paid: bool = False


class SessionRequest(BaseModel):
    pharmacy_name: str
    contact_email: str

class DualScoreResponse(BaseModel):
    deterministic_technical_score: int = Field(ge=0, le=100)
    self_attested_score: float = Field(ge=0.0, le=1.0)
    self_attested_grade: Literal["A","B","C","D","F"]
    risk_tier: Literal["LOW","MEDIUM","HIGH","CRITICAL"]
    attestation_verdict: Literal[
        "COMPLIANT","NON_COMPLIANT","CRITICAL_FAILURE"
    ]
    score_delta: int   # technical - attested*100 (divergence signal)
    flags: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    audit_log_id: str | None = None


class FacilityCreate(BaseModel):
    """Request model for creating a new facility."""
    name: str = Field(..., min_length=1)
    gln: str = Field(..., min_length=10)


class FacilityResponse(BaseModel):
    """Response model for facility details."""
    id: UUID
    tenant_id: UUID
    name: str
    gln: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TenantCreate(BaseModel):
    """Request model for creating a new tenant."""
    name: str = Field(..., min_length=1)


class TenantResponse(BaseModel):
    """Response model for tenant details."""
    id: UUID
    name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
