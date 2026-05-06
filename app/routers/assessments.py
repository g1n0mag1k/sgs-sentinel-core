from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import DualScoreRequest, DualScoreResponse
from app.services.scoring import calculate_dual_score, evaluate_dscsa_risk, score_attestation

router = APIRouter(prefix="/api/v1/assessment", tags=["assessment"])


@router.post("/dual-score", response_model=DualScoreResponse)
async def dual_score_assessment(
    payload: DualScoreRequest,
    db: AsyncSession = Depends(get_db),
) -> DualScoreResponse:
    """Evaluate dual-score assessment from EPCIS payload and attestation."""
    try:
        # Demo-friendly: use a stable tenant id unless auth is wired.
        tenant_id = uuid.UUID(int=0)
        technical = await evaluate_dscsa_risk(payload.epcis_payload, db, tenant_id)
        attested_score, attested_grade, gaps = score_attestation(payload.attestation)
        combined = calculate_dual_score(
            technical,
            attested_score,
            attested_grade,
            technical.flags,
            gaps,
        )
        return DualScoreResponse(
            **combined.model_dump(),
            audit_log_id=str(uuid.uuid4()),
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=500, detail=str(exc))
