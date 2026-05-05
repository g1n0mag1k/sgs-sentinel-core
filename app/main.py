from __future__ import annotations

import hashlib

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import AuditLog, User
from app.routers import auth as auth_router
from app.routers import facilities as facilities_router
from app.routers import tenants as tenants_router
from app.routers import users as users_router
from app.schemas import ScoreRequest, ScoreResponse
from app.services.scoring import evaluate_dscsa_risk

app = FastAPI(title="SGS-Sentinel Core", version="0.1.0")

app.include_router(auth_router.router)
app.include_router(tenants_router.router)
app.include_router(facilities_router.router)
app.include_router(users_router.router)


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
        score = await evaluate_dscsa_risk(request.payload)

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