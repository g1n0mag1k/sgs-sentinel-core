from __future__ import annotations

import hashlib

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import AuditLog, User
from app.routers import auth as auth_router
from app.routers import facilities as facilities_router
from app.routers import tenants as tenants_router
from app.schemas import ScoreRequest, ScoreResponse, DualScoreRequest, DualScoreResponse
from app.services.scoring import evaluate_dscsa_risk, score_attestation, calculate_dual_score

app = FastAPI(title="SGS-Sentinel Core", version="0.1.0")

app.include_router(auth_router.router)
app.include_router(tenants_router.router)
app.include_router(facilities_router.router)

# Define the origins that are allowed to make requests to this API
origins = [
    "https://sui-g3n3ri.me",         # Your live production site
    "http://localhost:3000",        # Common for local dev
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Restricts access to your specific domains
    allow_credentials=True,          # Allows the browser to send cookies/auth headers
    allow_methods=["*"],             # Allows POST, GET, OPTIONS, etc.
    allow_headers=["*"],             # Allows Authorization and Content-Type headers
)


@app.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Verify database connectivity."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/v1/assessment/score", response_model=ScoreResponse)
async def score_assessment(
    request: ScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScoreResponse:
    """Score an EPCIS payload and write an immutable chained audit record."""
    try:
        # Evaluate technical DSCSA risk score
        score = await evaluate_dscsa_risk(request.payload, db, current_user.tenant_id)

        # Compute prev_hash from most recent audit log for this tenant
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == current_user.tenant_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
        last_log = result.scalar_one_or_none()
        prev_hash = (
            hashlib.sha256(
                f"{last_log.id}{last_log.timestamp}{last_log.action}".encode()
            ).hexdigest()
            if last_log
            else None
        )

        # Write full response to audit log payload (JSONB column)
        db.add(
            AuditLog(
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                action="assessment.score",
                resource="dscsa_assessment",
                prev_hash=prev_hash,
                payload={
                    "request": request.model_dump(),
                    "response": score.model_dump(),
                },
            )
        )
        await db.commit()
        return score
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Assessment scoring failed") from exc


@app.post("/api/v1/assessment/dual-score", response_model=DualScoreResponse)
async def dual_score_assessment(
    request: DualScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DualScoreResponse:
    """Score EPCIS payload and self-attestation, return combined DualScoreResponse.
    
    The response includes both technical flags and attestation gaps, saved to audit trail.
    """
    try:
        # Evaluate technical DSCSA risk score
        technical_score = await evaluate_dscsa_risk(
            request.epcis_payload, db, current_user.tenant_id
        )
        
        # Score the attestation responses
        attestation_score, attestation_grade, gaps = score_attestation(request.attestation)
        
        # Calculate combined dual score
        response = calculate_dual_score(
            technical_score=technical_score,
            attestation_score=attestation_score,
            attestation_grade=attestation_grade,
            flags=technical_score.flags,
            gaps=gaps,
        )

        # Compute prev_hash from most recent audit log for this tenant
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == current_user.tenant_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
        last_log = result.scalar_one_or_none()
        prev_hash = (
            hashlib.sha256(
                f"{last_log.id}{last_log.timestamp}{last_log.action}".encode()
            ).hexdigest()
            if last_log
            else None
        )

        # Write full DualScoreResponse to audit log payload (JSONB column)
        db.add(
            AuditLog(
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                action="assessment.dual_score",
                resource="dscsa_assessment",
                prev_hash=prev_hash,
                payload={
                    "request": request.model_dump(),
                    "response": response.model_dump(),  # Full response with flags and gaps
                },
            )
        )
        await db.commit()
        return response
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Dual score assessment failed") from exc