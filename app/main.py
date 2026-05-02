from __future__ import annotations

from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLog
from app.schemas import ScoreRequest, ScoreResponse
from app.services.scoring import evaluate_dscsa_risk

app = FastAPI(title="SGS-Sentinel Core", version="0.1.0")


@app.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Verify database connectivity."""

    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/v1/assessment/score", response_model=ScoreResponse)
async def score_assessment(
    request: ScoreRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    user_id: UUID | None = Header(default=None, alias="X-User-ID"),
) -> ScoreResponse:
    """Score an EPCIS payload and write an immutable audit record."""

    try:
        score = await evaluate_dscsa_risk(request.model_dump())

        db.add(
            AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action="assessment.score",
                resource="dscsa_assessment",
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