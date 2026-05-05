from typing import Literal, Any
from pydantic import BaseModel, Field

AttestationAnswer = Literal["yes", "partial", "no"]

class M1M6Attestation(BaseModel):
    answers: dict[str, AttestationAnswer]
    # e.g. {"M1-Q1": "yes", "M2-Q3": "partial", ...}
    submitted_glns: list[str] = Field(default_factory=list)

class DualScoreRequest(BaseModel):
    epcis_payload: dict[str, Any]
    attestation: M1M6Attestation
    facility_name: str

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